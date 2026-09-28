local({p <- c("readxl", "dplyr", "tidyr", "purrr", "readr", "stringr", "zoo", "signal", "ggplot2", "patchwork"); missing <- p[!vapply(p, requireNamespace, logical(1), quietly = TRUE)]; if (length(missing)) install.packages(missing, repos = "https://cloud.r-project.org")})

# TrackScan: reproducible analysis of phyphox E Line recordings.
# In RStudio, open this file and click Source. No working-directory change needed.
# The checks at the end are calculated from the workbooks, never hard-coded results.
# Only the first line installs packages; subsequent runs reuse installed packages.
suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(patchwork)
})
# Namespace every data filter and signal filter to prevent name conflicts.

data_dir <- path.expand("~/Downloads/ORIGIN WEEKEND PRIMARY RESEARCH/")
ref_dir <- file.path(data_dir, "TrackScan Results", "code")
out_dir <- file.path(data_dir, "TrackScan Results", "R_output")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
tz_local <- "America/Los_Angeles"
M_LON <- 111320 * cos(34.03 * pi / 180)
M_LAT <- 110950
BIN_M <- 25
N_SHUFFLES <- 2000L

num <- function(x) suppressWarnings(as.numeric(x))
finite_median <- function(x) {
  x <- x[is.finite(x)]
  if (length(x)) median(x) else NA_real_
}
require_cols <- function(x, wanted, label) {
  missing <- setdiff(wanted, names(x))
  if (length(missing)) stop(label, ": missing columns: ", paste(missing, collapse = ", "))
}
read_ref <- function(name, columns) {
  x <- readr::read_csv(file.path(ref_dir, name), show_col_types = FALSE)
  require_cols(x, columns, name)
  x
}
shape <- read_ref("eline_shape.csv", c("seq", "lat", "lon")) %>%
  mutate(across(everything(), num)) %>% arrange(seq)
stations <- read_ref("eline_stations.csv", c("name", "lat", "lon", "chainage_m")) %>%
  mutate(across(c(lat, lon, chainage_m), num)) %>% arrange(chainage_m)
stops <- read_ref("stops_corridor.csv", c("stop_name", "stop_lat", "stop_lon")) %>%
  mutate(across(c(stop_lat, stop_lon), num)) %>%
  dplyr::filter(is.finite(stop_lat), is.finite(stop_lon))
stopifnot(nrow(shape) >= 2L, nrow(stations) >= 2L,
          all(is.finite(as.matrix(shape))),
          all(is.finite(stations$chainage_m)), !anyDuplicated(shape$seq))

# Geometry: retain cumulative distance even if the shape has repeated vertices.
sx <- shape$lon * M_LON
sy <- shape$lat * M_LAT
dx <- diff(sx)
dy <- diff(sy)
seg_length <- sqrt(dx^2 + dy^2)
cum_s <- c(0, cumsum(seg_length))
keep_segment <- which(seg_length > 0)
stopifnot(length(keep_segment) > 0)
seg_x <- sx[keep_segment]
seg_y <- sy[keep_segment]
seg_dx <- dx[keep_segment]
seg_dy <- dy[keep_segment]
seg_len <- seg_length[keep_segment]
seg_start <- cum_s[keep_segment]

snap_track <- function(lat, lon) {
  # All points against all nonzero-length track segments, with vectorized matrices.
  px <- lon * M_LON
  py <- lat * M_LAT
  rx <- outer(px, seg_x, "-")
  ry <- outer(py, seg_y, "-")
  fraction <- sweep(sweep(rx, 2, seg_dx, "*") +
                      sweep(ry, 2, seg_dy, "*"), 2, seg_len^2, "/")
  fraction[] <- pmax(0, pmin(1, fraction))
  ex <- rx - sweep(fraction, 2, seg_dx, "*")
  ey <- ry - sweep(fraction, 2, seg_dy, "*")
  distance2 <- ex^2 + ey^2
  best <- max.col(-distance2, ties.method = "first")
  index <- cbind(seq_along(px), best)
  tibble(s = seg_start[best] + fraction[index] * seg_len[best],
         offset_m = sqrt(distance2[index]))
}
point_at <- function(s) {
  tibble(lat = approx(cum_s, shape$lat, xout = s, rule = 2, ties = "ordered")$y,
         lon = approx(cum_s, shape$lon, xout = s, rule = 2, ties = "ordered")$y)
}
interpolate <- function(t, y, at) approx(t, y, xout = at, rule = 2)$y
nearest_gap <- function(t, at) {
  left <- findInterval(at, t)
  right <- pmin(length(t), left + 1L)
  left <- pmax(1L, left)
  pmin(abs(at - t[left]), abs(at - t[right]))
}
rolling <- function(x, width, method, minimum = 1L) {
  zoo::rollapply(x, width, function(z) {
    z <- z[is.finite(z)]
    if (length(z) < minimum) NA_real_ else method(z)
  }, align = "center", partial = TRUE, fill = NA_real_)
}
derivative <- function(v, t) {
  # Centered derivative; one-sided at the ends of each finite run.
  # Missing values are never converted to zeros or treated as stops.
  ans <- rep(NA_real_, length(v))
  good <- which(is.finite(v))
  if (!length(good)) return(ans)
  groups <- split(good, cumsum(c(TRUE, diff(good) != 1L)))
  for (ix in groups) {
    n <- length(ix)
    if (n < 2L) next
    ans[ix[1]] <- (v[ix[2]] - v[ix[1]]) / (t[ix[2]] - t[ix[1]])
    ans[ix[n]] <- (v[ix[n]] - v[ix[n - 1]]) / (t[ix[n]] - t[ix[n - 1]])
    if (n > 2L) {
      a <- ix[seq_len(n - 2L)]
      b <- ix[3:n]
      ans[ix[2:(n - 1L)]] <- (v[b] - v[a]) / (t[b] - t[a])
    }
  }
  ans
}
zero_phase <- function(filter_object, x, fs, pad_seconds) {
  # signal::filtfilt has different edge handling from scipy's sosfiltfilt.
  # Reflect extra data at both ends, filter, and trim to reduce edge transients.
  # Padding changes no timestamps and removes no measured windows.
  p <- min(length(x) - 1L, ceiling(pad_seconds * fs))
  padded <- c(2 * x[1] - rev(x[2:(p + 1L)]), x,
              2 * x[length(x)] - rev(x[(length(x) - p):(length(x) - 1L)]))
  result <- as.numeric(signal::filtfilt(filter_object, padded))
  result <- result[p + seq_along(x)]
  if (any(!is.finite(result))) stop("Nonfinite filter output; check sampling rate/data.")
  result
}

process_recording <- function(file, recording) {
  cat(sprintf("Processing %02d: %s\n", recording, basename(file)))
  a <- readxl::read_excel(file, sheet = "Accelerometer")
  g <- readxl::read_excel(file, sheet = "Location")
  meta <- readxl::read_excel(file, sheet = "Metadata Time")
  require_cols(a, c("Time (s)", "X (m/s^2)", "Y (m/s^2)", "Z (m/s^2)"), basename(file))
  require_cols(g, c("Time (s)", "Latitude (°)", "Longitude (°)",
                    "Velocity (m/s)", "Horizontal Accuracy (m)"), basename(file))
  require_cols(meta, c("event", "system time"), basename(file))
  epoch <- num(meta[["system time"]][toupper(trimws(meta$event)) == "START"])
  epoch <- epoch[is.finite(epoch)]
  if (!length(epoch)) stop(basename(file), ": missing START epoch.")
  start_events <- length(epoch)
  # phyphox writes another START after a pause/resume. The first START anchors
  # the shared experiment clock and ride grouping, as in the Python reference.
  epoch <- epoch[1]
  if (start_events > 1L) cat("  Pause/resume metadata: using the first START for ride grouping.\n")
  a <- a %>% transmute(t = num(`Time (s)`), x = num(`X (m/s^2)`),
                       y = num(`Y (m/s^2)`), z = num(`Z (m/s^2)`)) %>%
    dplyr::filter(if_all(everything(), is.finite)) %>%
    arrange(t) %>% distinct(t, .keep_all = TRUE)
  if (nrow(a) < 200L) stop(basename(file), ": too few accelerometer samples.")
  step <- median(diff(a$t))
  fs <- 1 / step
  if (!is.finite(fs) || fs <= 60) stop(basename(file), ": 30 Hz needs fs > 60 Hz.")
  if (max(diff(a$t)) > 0.5) warning(basename(file), ": accelerometer gap > 0.5 s; inspect export.")
  uniform_t <- seq(a$t[1], tail(a$t, 1), by = step)
  A <- vapply(a[c("x", "y", "z")], function(v) interpolate(a$t, v, uniform_t),
              numeric(length(uniform_t)))
  gravity_filter <- signal::butter(2, 0.3 / (fs / 2), type = "low")
  G <- apply(A, 2, function(v) zero_phase(gravity_filter, v, fs, 10))
  gravity_size <- sqrt(rowSums(G^2))
  if (any(gravity_size < 1e-6)) stop("Cannot estimate gravity in ", basename(file))
  vertical <- rowSums(A * G) / gravity_size
  vibration_filter <- signal::butter(4, c(1, 30) / (fs / 2), type = "pass")
  vibration <- zero_phase(vibration_filter, vertical - mean(vertical), fs, 3)

  # True one-second bins, anchored at the first sample. Discard the incomplete end.
  # This avoids accumulating timing drift when fs is not an integer.
  n_windows <- floor(tail(uniform_t, 1) - uniform_t[1])
  window_id <- floor(uniform_t - uniform_t[1])
  windows <- tibble(window_id, square = vibration^2) %>%
    dplyr::filter(window_id < n_windows) %>% group_by(window_id) %>%
    summarise(rms = sqrt(mean(square)), .groups = "drop") %>%
    mutate(t = uniform_t[1] + window_id + 0.5)
  if (nrow(windows) < 10L) stop(basename(file), ": recording too short.")

  gps_raw <- nrow(g)
  g <- g %>% transmute(t = num(`Time (s)`), lat = num(`Latitude (°)`),
                       lon = num(`Longitude (°)`), velocity = num(`Velocity (m/s)`),
                       accuracy = num(`Horizontal Accuracy (m)`)) %>%
    dplyr::filter(is.finite(t), is.finite(lat), is.finite(lon),
                 is.na(accuracy) | accuracy <= 40) %>%
    arrange(t) %>% distinct(t, .keep_all = TRUE)
  # An unknown accuracy is retained: the specified rule excludes only > 40 m.
  if (nrow(g) < 2L) stop(basename(file), ": fewer than two usable GPS fixes.")
  lat <- interpolate(g$t, g$lat, windows$t)
  lon <- interpolate(g$t, g$lon, windows$t)
  snapped <- snap_track(lat, lon)
  gps_gap <- nearest_gap(g$t, windows$t)
  located <- gps_gap <= 4 & snapped$offset_m <= 60

  # Retain the regular timeline for derivatives and stop buffers. Invalid locations
  # cannot contribute scores, fallback speeds, or artificial zero-speed stops.
  s_for_speed <- ifelse(located, snapped$s, NA_real_)
  ds_speed <- abs(c(NA_real_, diff(s_for_speed) / diff(windows$t)))
  fallback_speed <- rolling(ds_speed, 5, median, minimum = 2L)
  # Keep missing GPS velocities as NA through interpolation; use the fallback
  # whenever interpolated velocity is missing or negative. Do not bridge NaNs.
  velocity <- g$velocity
  velocity[!is.finite(velocity) | velocity < 0] <- NA_real_
  gps_speed <- approx(g$t, velocity, xout = windows$t, rule = 2, na.rm = FALSE)$y
  speed <- ifelse(is.finite(gps_speed) & gps_speed >= 0, gps_speed, fallback_speed)
  speed[!located] <- NA_real_
  filled_speed <- zoo::na.approx(speed, x = windows$t, maxgap = 5,
                                 na.rm = FALSE, rule = 1)
  smooth_speed <- rolling(filled_speed, 3, mean)
  long_acc <- derivative(smooth_speed, windows$t)
  stopped <- is.finite(smooth_speed) & smooth_speed < 1
  stop_times <- windows$t[stopped]
  until_stop <- since_stop <- rep(Inf, nrow(windows))
  if (length(stop_times)) {
    previous <- findInterval(windows$t, stop_times)
    has_previous <- previous > 0L
    since_stop[has_previous] <- windows$t[has_previous] - stop_times[previous[has_previous]]
    next_index <- previous + 1L
    has_next <- next_index <= length(stop_times)
    until_stop[has_next] <- stop_times[next_index[has_next]] - windows$t[has_next]
    until_stop[stopped] <- 0
  }
  phase <- dplyr::case_when(
    long_acc < -0.3 | until_stop <= 10 ~ "braking", # Braking wins ties.
    long_acc > 0.3 | since_stop <= 10 ~ "accelerating",
    TRUE ~ "cruise"
  )
  moving <- located & is.finite(speed) & speed >= 3
  if (any(moving & !is.finite(long_acc))) {
    stop(basename(file), ": moving windows with unknown acceleration; inspect GPS gaps.")
  }
  w <- bind_cols(windows, snapped) %>%
    mutate(speed = speed, long_acc = long_acc, phase = phase,
           gps_gap_s = gps_gap, recording = recording) %>% dplyr::filter(moving)
  if (nrow(w) < 20L) stop(basename(file), ": too few moving, located windows.")
  trend <- unname(coef(lm(s ~ t, data = w))["t"])
  if (!is.finite(trend) || abs(trend) < 1e-6) stop("Direction is indeterminate: ", basename(file))
  direction <- if (trend > 0) "WB" else "EB"
  summary <- tibble(recording, file = basename(file), direction, start_epoch = epoch,
                    duration_min = (tail(a$t, 1) - a$t[1]) / 60,
                    km_covered = diff(range(w$s)) / 1000,
                    moving_seconds = nrow(w),
                    pct_cruise = 100 * mean(w$phase == "cruise"),
                    pct_braking = 100 * mean(w$phase == "braking"),
                    pct_accelerating = 100 * mean(w$phase == "accelerating"),
                    median_cruise_speed_kmh = 3.6 * finite_median(w$speed[w$phase == "cruise"]),
                    gps_fixes = nrow(g), gps_fixes_raw = gps_raw, sample_rate_hz = fs,
                    start_events = start_events)
  list(summary = summary, windows = w)
}

# Nonrecursive: only workbooks in the input folder, excluding Excel lock files.
files <- sort(list.files(data_dir, pattern = "\\.xlsx$", full.names = TRUE, ignore.case = TRUE))
files <- files[!stringr::str_starts(basename(files), "~\\$") & !dir.exists(files)]
if (!length(files)) stop("No .xlsx recordings in ", data_dir)
# Fail visibly on an unusable recording: silently skipping it changes the denominator.
processed <- purrr::map2(files, seq_along(files), process_recording)
summary <- purrr::map_dfr(processed, "summary") %>% arrange(start_epoch, file) %>%
  mutate(ride_id = cumsum(c(TRUE, diff(start_epoch) > 180)),
         start_time = format(as.POSIXct(start_epoch, origin = "1970-01-01", tz = tz_local),
                             "%Y-%m-%d %H:%M:%S %Z", tz = tz_local))
ride_info <- summary %>% group_by(ride_id) %>%
  summarise(start_epoch = min(start_epoch), phones = n(),
            direction_count = n_distinct(direction), direction = first(direction), .groups = "drop")
if (any(ride_info$direction_count != 1L)) stop("Conflicting phone directions within a ride; inspect START grouping.")
ride_info <- ride_info %>% mutate(
  local_hm = format(as.POSIXct(start_epoch, origin = "1970-01-01", tz = tz_local), "%H:%M", tz = tz_local),
  ride = sprintf("Ride %d · %s · %s", ride_id, local_hm, direction))
summary <- summary %>% left_join(select(ride_info, ride_id, ride), by = "ride_id")
moving <- purrr::map_dfr(processed, "windows") %>%
  left_join(select(summary, recording, ride_id, direction), by = "recording")
n_recordings <- nrow(summary)
n_rides <- nrow(ride_info)
phase_share <- moving %>% count(phase, name = "seconds") %>%
  tidyr::complete(phase = c("cruise", "braking", "accelerating"), fill = list(seconds = 0L)) %>%
  mutate(percent = 100 * seconds / sum(seconds))
cat("\nPhase share of ALL moving windows (before cruise-only selection):\n")
print(phase_share, n = Inf)

# Everything scored from here down uses ONLY cruise windows.
cruise <- moving %>% dplyr::filter(phase == "cruise")
if (any(!is.finite(cruise$rms) | cruise$rms <= 0)) stop("Nonpositive/invalid cruise RMS cannot be log-fitted.")
if (n_distinct(cruise$recording) != n_recordings) stop("A recording has no cruise data; do not silently change coverage.")
if (n_distinct(cruise$speed) < 2L) stop("Insufficient speed variation to fit speed adjustment.")
speed_model <- lm(log(rms) ~ log(speed), data = cruise)
b_raw <- unname(coef(speed_model)["log(speed)"])
if (!is.finite(b_raw)) stop("Speed exponent is not estimable.")
b <- max(0, min(2, b_raw))
cruise <- cruise %>% mutate(adj = rms / speed^b) %>% group_by(recording) %>%
  mutate(score = adj / median(adj),
         hot_threshold = as.numeric(quantile(score, 0.90, type = 7))) %>%
  ungroup() %>% mutate(bin = as.integer(floor(s / BIN_M)))

# Each recording contributes at most one value to a bin, regardless of its speed.
recording_bins <- cruise %>% group_by(recording, ride_id, direction, bin) %>%
  summarise(score = max(score), hot_threshold = first(hot_threshold), .groups = "drop") %>%
  mutate(hot = score >= hot_threshold)
bins <- recording_bins %>% group_by(bin) %>%
  summarise(recordings_covering = n(), median_score = median(score),
            hot_fraction = mean(hot), .groups = "drop") %>% arrange(bin) %>%
  mutate(start_m = bin * BIN_M, end_m = start_m + BIN_M,
         center_m = start_m + BIN_M / 2,
         hotspot = recordings_covering >= ceiling(0.5 * n_recordings) &
           hot_fraction >= 0.5 & median_score >= 1.5)
ride_bins <- recording_bins %>% group_by(ride_id, bin) %>%
  summarise(hot = any(hot), phones_covering = n(), .groups = "drop")

# Merge adjacent qualifying bins first, then segment gaps <= 75 m.
candidates <- bins %>% dplyr::filter(hotspot)
candidates$segment <- if (nrow(candidates)) cumsum(c(TRUE, diff(candidates$bin) != 1L)) else integer()
segments <- candidates %>% group_by(segment) %>%
  summarise(start_m = min(start_m), end_m = max(end_m), .groups = "drop") %>% arrange(start_m)
if (nrow(segments)) {
  segments <- segments %>% mutate(zone = cumsum(c(TRUE, start_m[-1] - head(end_m, -1) > 75)))
}
zone_bounds <- if (nrow(segments)) {
  segments %>% group_by(zone) %>%
    summarise(start_m = min(start_m), end_m = max(end_m), .groups = "drop")
} else tibble(zone = integer(), start_m = double(), end_m = double())

describe_zone <- function(zone, start_m, end_m) {
  # Include the entire merged interval, including its small intervening gaps.
  z <- bins %>% dplyr::filter(.data$start_m >= .env$start_m, .data$start_m < .env$end_m)
  peak <- z %>% arrange(desc(median_score), bin) %>% slice(1)
  rb <- ride_bins %>% dplyr::filter(bin %in% z$bin)
  rough <- unique(rb$ride_id[rb$hot])
  covered <- unique(rb$ride_id)
  rough_directions <- ride_info$direction[match(rough, ride_info$ride_id)]
  peak_m <- peak$center_m
  ll <- point_at(peak_m)
  near <- which.min(abs(stations$chainage_m - peak_m))
  before <- which(stations$chainage_m <= peak_m)
  after <- which(stations$chainage_m > peak_m)
  between <- paste0("between ", if (length(before)) stations$name[max(before)] else "line start",
                    " → ", if (length(after)) stations$name[min(after)] else "line end")
  cross_street <- NA_character_
  if (nrow(stops)) {
    distance <- sqrt(((stops$stop_lon - ll$lon) * M_LON)^2 +
                       ((stops$stop_lat - ll$lat) * M_LAT)^2)
    j <- which.min(distance)
    if (distance[j] <= 150) cross_street <- stops$stop_name[j]
  }
  distance_station <- abs(stations$chainage_m[near] - peak_m)
  # Station flag and location labels use the peak, also used for the Maps link.
  tibble(zone, start_m, end_m, length_m = end_m - start_m, peak_bin = peak$bin,
         peak_m, severity = peak$median_score,
         recordings_covering_peak = peak$recordings_covering,
         hot_fraction_peak = peak$hot_fraction,
         rides_rough = length(rough), rides_covering = length(covered),
         rough_ride_ids = paste(sort(rough), collapse = ";"),
         covering_ride_ids = paste(sort(covered), collapse = ";"),
         both_directions = all(c("WB", "EB") %in% rough_directions),
         nearest_station = stations$name[near], dist_to_station_m = distance_station,
         between, cross_street, station_zone = distance_station <= 150,
         lat = ll$lat, lon = ll$lon,
         google_maps = sprintf("https://www.google.com/maps?q=%.7f,%.7f", ll$lat, ll$lon))
}
# A typed empty result still produces a CSV with headers and a valid chart.
zones <- if (nrow(zone_bounds)) purrr::pmap_dfr(zone_bounds, describe_zone) else {
  tibble(zone = integer(), start_m = double(), end_m = double(), length_m = double(),
         peak_bin = integer(), peak_m = double(), severity = double(),
         recordings_covering_peak = integer(), hot_fraction_peak = double(),
         rides_rough = integer(), rides_covering = integer(), rough_ride_ids = character(),
         covering_ride_ids = character(), both_directions = logical(), nearest_station = character(),
         dist_to_station_m = double(), between = character(), cross_street = character(),
         station_zone = logical(), lat = double(), lon = double(), google_maps = character())
}
zones <- zones %>% dplyr::filter(rides_rough >= 3) %>%
  mutate(repeat_fraction = rides_rough / rides_covering,
         rank_score = severity * repeat_fraction * ifelse(both_directions, 1.25, 1)) %>%
  arrange(desc(rank_score), desc(severity), start_m) %>%
  mutate(rank = row_number()) %>% select(rank, everything())

# Chance test: restrict to common cruise coverage BEFORE building the sequences.
# A ride is hot if any of its phones is hot. Missing coverage is never FALSE.
# Common bins are ordered by chainage; circular shifts operate on that restricted
# sequence (so gaps between common bins are compressed, as specified).
common_bins <- ride_bins %>% count(bin, name = "rides_covering") %>%
  dplyr::filter(rides_covering == n_rides) %>% arrange(bin)
observed_all <- shuffle_mean <- shuffle_max <- chance_p <- NA_real_
shuffle_counts <- integer()
if (nrow(common_bins)) {
  matrix_table <- ride_bins %>% dplyr::filter(bin %in% common_bins$bin) %>%
    select(bin, ride_id, hot) %>% tidyr::pivot_wider(names_from = ride_id, values_from = hot) %>% arrange(bin)
  hot_matrix <- as.matrix(select(matrix_table, -bin))
  stopifnot(ncol(hot_matrix) == n_rides, !anyNA(hot_matrix))
  observed_all <- sum(rowSums(hot_matrix) == n_rides)
  n_common <- nrow(hot_matrix)
  set.seed(0)
  shuffle_counts <- replicate(N_SHUFFLES, {
    offsets <- sample.int(n_common, n_rides, replace = TRUE) - 1L
    shifted <- vapply(seq_len(n_rides), function(j) {
      hot_matrix[((seq_len(n_common) - 1L + offsets[j]) %% n_common) + 1L, j]
    }, logical(n_common))
    # matrix() also handles the single-common-bin or single-ride case.
    shifted <- matrix(shifted, nrow = n_common, ncol = n_rides)
    sum(rowSums(shifted) == n_rides)
  })
  shuffle_mean <- mean(shuffle_counts)
  shuffle_max <- max(shuffle_counts)
  chance_p <- (1 + sum(shuffle_counts >= observed_all)) / (N_SHUFFLES + 1)
}

# Write the requested tables without premature rounding of scores/ranks.
readr::write_csv(zones, file.path(out_dir, "hotspots_R.csv"), na = "")
recordings_summary <- summary %>% select(file, ride, direction, start_time,
  duration_min, km_covered, moving_seconds, pct_cruise, pct_braking, pct_accelerating,
  median_cruise_speed_kmh, gps_fixes, gps_fixes_raw, sample_rate_hz, start_events, recording, ride_id, start_epoch)
readr::write_csv(recordings_summary, file.path(out_dir, "recordings_summary_R.csv"), na = "")

# Chart: gray profiles use each ride's median WINDOW score in each bin.
# The blue profile uses the median of the per-recording bin MAXIMA (step 14).
# Make gaps explicit so lines cannot bridge unobserved bins.
ride_profiles <- cruise %>% group_by(ride_id, bin) %>%
  summarise(score = median(score), .groups = "drop") %>%
  tidyr::complete(ride_id, bin = seq.int(min(bins$bin), max(bins$bin))) %>%
  mutate(km = (bin * BIN_M + BIN_M / 2) / 1000)
blue_profile <- bins %>% select(bin, median_score) %>%
  tidyr::complete(bin = seq.int(min(bins$bin), max(bins$bin))) %>%
  mutate(km = (bin * BIN_M + BIN_M / 2) / 1000)
# Draw separate coverage bars across contiguous cruise bins, preserving gaps.
coverage_bars <- ride_bins %>% arrange(ride_id, bin) %>% group_by(ride_id) %>%
  mutate(piece = cumsum(c(TRUE, diff(bin) != 1L))) %>% group_by(ride_id, piece) %>%
  summarise(x = min(bin) * BIN_M / 1000,
            xend = (max(bin) + 1) * BIN_M / 1000, .groups = "drop")
dots <- ride_bins %>% dplyr::filter(hot) %>% mutate(km = (bin * BIN_M + BIN_M / 2) / 1000)
station_ticks <- stations %>% dplyr::filter(chainage_m >= 15281, chainage_m <= 24901) %>%
  mutate(label = stringr::str_remove(name, " / Ethel Bradley"),
         label = stringr::str_remove(label, " E-Line$"))
x_limits <- range(c(bins$start_m, bins$end_m, station_ticks$chainage_m)) / 1000 + c(-0.10, 0.10)
profile_max <- max(c(ride_profiles$score, blue_profile$median_score), na.rm = TRUE)
top5 <- zones %>% slice_head(n = 5) %>% arrange(peak_m) %>%
  mutate(peak_km = peak_m / 1000,
         label = sprintf("#%d  %.1f×\n%d/%d rides", rank, severity, rides_rough, rides_covering))
# Manual label placement: enforce minimum horizontal separation, use a reserved
# row above every profile, and connect each label to its actual peak.
if (nrow(top5)) {
  separation <- diff(x_limits) * 0.13
  label_x <- pmax(x_limits[1] + separation / 2, top5$peak_km)
  if (length(label_x) > 1L) for (i in 2:length(label_x)) {
    label_x[i] <- max(label_x[i], label_x[i - 1L] + separation)
  }
  label_x[length(label_x)] <- min(tail(label_x, 1), x_limits[2] - separation / 2)
  if (length(label_x) > 1L) for (i in seq.int(length(label_x) - 1L, 1L)) {
    label_x[i] <- min(label_x[i], label_x[i + 1L] - separation)
  }
  top5$label_x <- label_x
  top5$label_y <- profile_max * 1.10
} else {
  top5$label_x <- numeric()
  top5$label_y <- numeric()
}
surface <- "#fcfcfb"
blue <- "#2a78d6"
red <- "#d03b3b"
base_theme <- theme_minimal(base_size = 10, base_family = "sans") +
  theme(plot.background = element_rect(fill = surface, colour = NA),
        panel.background = element_rect(fill = surface, colour = NA),
        panel.grid.minor = element_blank(), panel.grid.major = element_line(colour = "#e7e6e0", linewidth = 0.25),
        axis.title = element_text(colour = "#52514e"), axis.text = element_text(colour = "#52514e"),
        plot.margin = margin(6, 15, 6, 6))
x_scale <- function() scale_x_continuous(limits = x_limits, breaks = station_ticks$chainage_m / 1000,
                                        labels = station_ticks$label, expand = expansion(mult = 0))
bands <- function() geom_rect(data = top5,
  aes(xmin = start_m / 1000, xmax = end_m / 1000, ymin = -Inf, ymax = Inf),
  inherit.aes = FALSE, fill = red, alpha = 0.08)
top <- ggplot() + bands() +
  geom_hline(yintercept = 1, colour = "#d7d6cf", linewidth = 0.35) +
  geom_line(data = ride_profiles, aes(km, score, group = ride_id), colour = "#c3c2b7", linewidth = 0.35, na.rm = TRUE) +
  geom_line(data = blue_profile, aes(km, median_score), colour = blue, linewidth = 1, na.rm = TRUE) +
  geom_segment(data = top5, aes(x = peak_km, xend = label_x, y = severity, yend = label_y - profile_max * 0.05),
               colour = "#99968f", linewidth = 0.3) +
  geom_point(data = top5, aes(peak_km, severity), colour = red, size = 2.7) +
  geom_label(data = top5, aes(label_x, label_y, label = label), size = 3,
             fill = surface, colour = "#202020", linewidth = 0, lineheight = 1.05) +
  x_scale() + scale_y_continuous(limits = c(0, profile_max * 1.23), expand = expansion(mult = 0)) +
  labs(x = NULL, y = "Shake vs. a typical stretch (×)",
       subtitle = "Gray: each ride's median window score   •   Blue: median of recording bin maxima") +
  base_theme + theme(axis.text.x = element_blank(), axis.ticks.x = element_blank(),
                     plot.subtitle = element_text(size = 8.5, colour = "#66645f"))
bottom <- ggplot() + bands() +
  geom_segment(data = coverage_bars, aes(x = x, xend = xend, y = ride_id, yend = ride_id),
               colour = "#e1e0d9", linewidth = 4, lineend = "butt") +
  geom_point(data = dots, aes(km, ride_id), colour = "#52514e", size = 1.1) +
  x_scale() + scale_y_reverse(breaks = ride_info$ride_id, labels = ride_info$ride,
                             limits = c(n_rides + 0.5, 0.5), expand = expansion(mult = 0)) +
  labs(x = NULL, y = NULL,
       caption = "Dots = that ride's roughest 10% of track. Columns of dots = the same spot, felt on every train.") +
  base_theme + theme(axis.text.x = element_text(angle = 30, hjust = 1, size = 8.5),
                     axis.text.y = element_text(size = 8.5), panel.grid.major.y = element_blank(),
                     plot.caption = element_text(hjust = 0, size = 8, colour = "#77756f", margin = margin(t = 9)))
# The requested note is shorthand: a dot actually means ANY phone on the ride
# exceeded its own 90th percentile of cruise WINDOW scores, not a ride quantile.
# Keep subtitle counts/date honest if the input folder changes in the future.
local_dates <- unique(format(as.POSIXct(summary$start_epoch, origin = "1970-01-01", tz = tz_local),
                             "%Y-%m-%d", tz = tz_local))
date_label <- if (identical(local_dates, "2026-09-26")) "Sept 26" else paste(local_dates, collapse = ", ")
subtitle <- sprintf(paste0("Vertical vibration along the Metro E Line, Expo Park/USC → Culver City · ",
                           "%d recordings on %d trains, %s · speed-adjusted · braking & accelerating removed"),
                    n_recordings, n_rides, date_label)
chart <- (top / bottom) + plot_layout(heights = c(2.35, 1.25)) +
  plot_annotation(title = "The same spots shake on every train", subtitle = subtitle,
    caption = "Method: gravity-aligned 1–30 Hz RMS / second; GPS snapped to track; cruise ≥3 m/s; speed-adjusted and phone-normalized; 25 m bins compared across rides.",
    theme = theme(plot.background = element_rect(fill = surface, colour = NA),
                  plot.title = element_text(face = "bold", size = 19, colour = "#151515"),
                  plot.subtitle = element_text(size = 8.5, colour = "#52514e", margin = margin(b = 10)),
                  plot.caption = element_text(size = 7.5, hjust = 0, colour = "#77756f"),
                  plot.margin = margin(14, 16, 12, 14)))
ggsave(file.path(out_dir, "chart_R.png"), chart, width = 13, height = 7.2,
       units = "in", dpi = 160, bg = surface)
# Show in RStudio's Plots pane; avoid an unwanted Rplots.pdf in batch runs.
if (interactive()) print(chart)

# Verification: expected figures are reference targets, never inputs to analysis.
# Soft comparisons flag discrepancies without forcing agreement with Python.
cat("\n================ COMPUTED CHECKS ================\n")
cat(sprintf("Recordings: %d; rides: %d. Reference: 11 recordings / 5 rides.\n", n_recordings, n_rides))
print(select(ride_info, ride, phones), n = Inf)
cat("Reference: Ride 1 09:34 WB (3); Ride 2 09:58 EB (2); Ride 3 10:07 EB (1); Ride 4 10:30 WB (3); Ride 5 11:25 EB (2).\n")
cat("\nCoverage in km (chainage span of moving windows; reference mostly ~9.6, one ~6.1):\n")
print(select(recordings_summary, file, km_covered), n = Inf)
cat(sprintf("\nMoving 1-second windows: %d; reference ~7,170.\n", nrow(moving)))
print(phase_share, n = Inf)
cat("Reference phase split: ~49% cruise / 27% braking / 24% accelerating.\n")
braking_acc <- finite_median(moving$long_acc[moving$phase == "braking"])
cat(sprintf("Median long_acc while braking: %.3f m/s^2; reference ~-0.7.\n", braking_acc))
cat(sprintf("Speed exponent: raw %.4f; clipped b %.4f; reference ~1.0.\n", b_raw, b))
cat("\nComputed ranked zones (station distances and labels refer to the peak):\n")
print(zones %>% select(rank, start_m, end_m, cross_street, nearest_station,
                       dist_to_station_m, severity, rides_rough, rides_covering, both_directions), n = Inf, width = Inf)
cat("Reference #1: ~16100–16250 m, Exposition / Budlong, ~3.4x, 5/5, both directions.\n",
    "Reference #2: ~17200–17225 m, Exposition / Harvard, ~2.9x, 3/3.\n",
    "Reference #3: ~17875–17900 m, ~2.2x, 4/4.\n", sep = "")
if (nrow(common_bins)) {
  cat(sprintf(paste0("\nChance test: %d common-coverage bins; %d bins hot on ALL %d rides.\n",
                     "%d independent circular-shift shuffles: mean %.4f, max %d; Monte Carlo p = %.5f.\n"),
              nrow(common_bins), observed_all, n_rides, N_SHUFFLES, shuffle_mean, shuffle_max, chance_p))
} else cat("\nChance test unavailable: no bins have cruise coverage on every ride.\n")
cat("Chance reference: 2 bins hot on all 5 rides vs ~0.05 expected by chance.\n")
checks <- tibble(
  check = c("11 recordings", "5 rides", "Ride times, directions and phone counts", "Moving windows within 10% of 7170",
            "Phase shares within 7 percentage points", "Braking median within 0.3 of -0.7",
            "Speed exponent within 0.3 of 1", "Top-three peak locations within 150 m", "Chance: observed 2, mean within 0.05 of 0.05"),
  pass = c(n_recordings == 11, n_rides == 5,
           identical(ride_info$local_hm, c("09:34", "09:58", "10:07", "10:30", "11:25")) &&
             identical(ride_info$direction, c("WB", "EB", "EB", "WB", "EB")) &&
             identical(ride_info$phones, c(3L, 2L, 1L, 3L, 2L)),
           abs(nrow(moving) - 7170) <= 717,
           all(abs(phase_share$percent - c(cruise = 49, braking = 27, accelerating = 24)[phase_share$phase]) <= 7),
           is.finite(braking_acc) && abs(braking_acc + 0.7) <= 0.3,
           abs(b - 1) <= 0.3,
           nrow(zones) >= 3 && all(abs(head(zones$peak_m, 3) - c(16175, 17212.5, 17887.5)) <= 150),
           is.finite(observed_all) && observed_all == 2 && abs(shuffle_mean - 0.05) <= 0.05)) %>%
  mutate(status = ifelse(pass, "OK", "REVIEW: compare computed results above")) %>% select(-pass)
cat("\nLoose diagnostic comparisons (not statistical acceptance criteria):\n")
print(checks, n = Inf, width = Inf)
cat("\nR/scipy edge handling, exact one-second boundaries, and missing-speed treatment can cause small differences.\n")
cat("Repeated vibration identifies inspection candidates; it does not by itself establish a track defect.\n")
cat("\nSaved:\n", paste(file.path(out_dir, c("hotspots_R.csv", "recordings_summary_R.csv", "chart_R.png")), collapse = "\n"), "\n")
cat("\nPackage/R versions for reproducibility:\n")
print(sessionInfo())
