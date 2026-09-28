// Pinetrack demo server: serves the static site and, when SMTP is configured, emails each automatic
// alert to the demo inbox. Without SMTP settings the site still works and alerts stay on screen.
'use strict';
const fs = require('fs');
const path = require('path');
const express = require('express');
const nodemailer = require('nodemailer');
const { RECIPIENT, rule, level, describe } = require('./alert-rules.js');

// The demo inbox standing in for the agency's track maintenance team. Set it here, or as a
// DEMO_ALERT_EMAIL secret / environment variable to keep the address out of the public repository.
const DEMO_ALERT_EMAIL = process.env.DEMO_ALERT_EMAIL || '[OUR TEAM EMAIL]';

const PORT = Number(process.env.PORT) || 3000;
const SMTP_PORT = Number(process.env.SMTP_PORT) || 587;
const { SMTP_HOST, SMTP_USER, SMTP_PASS } = process.env;
// A public demo must not flood the inbox: each spot at most once per 30 seconds, plus an hourly cap.
const SPOT_COOLDOWN_MS = 30 * 1000;
const MAX_PER_HOUR = Number(process.env.ALERT_MAX_PER_HOUR) || 60;

const readData = name => JSON.parse(fs.readFileSync(path.join(__dirname, 'data', name), 'utf8'));
const summary = readData('summary.json');
const recordings = readData('recordings.json');
const spots = new Map(readData('hotspots.geojson').features.filter(f => f.geometry.type === 'Point').map(f => [f.properties.id, f]));
const alertRule = rule(summary);

const missing = [
  !SMTP_HOST && 'SMTP_HOST', !SMTP_USER && 'SMTP_USER', !SMTP_PASS && 'SMTP_PASS',
  !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(DEMO_ALERT_EMAIL) && 'DEMO_ALERT_EMAIL'
].filter(Boolean);
const mailer = missing.length ? null : nodemailer.createTransport({ host: SMTP_HOST, port: SMTP_PORT, secure: SMTP_PORT === 465, auth: { user: SMTP_USER, pass: SMTP_PASS } });

// The page reads this meta tag to decide whether to call /api/alert, so a static host never gets a failing request.
const EMAIL_FLAG = '<meta name="pinetrack-email" content="off">';
const indexHtml = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
if (!indexHtml.includes(EMAIL_FLAG)) console.warn('index.html has no pinetrack-email meta tag; the page will not request alert emails.');
const page = indexHtml.replace(EMAIL_FLAG, `<meta name="pinetrack-email" content="${mailer ? 'on' : 'off'}">`);

function emailText(a) {
  return [
    `Sent automatically by Pinetrack to ${RECIPIENT} (demo inbox).`,
    '',
    'Alert level: Inspect (meets the Pinetrack rule)',
    `What: ${a.what}`,
    `Where: ${a.where}`,
    `Direction: ${a.route}`,
    `Lat/lon: ${a.latlon} (approximate)`,
    `Map: ${a.mapUrl}`,
    '',
    `Evidence (${a.recorded}):`,
    ...a.passes.map(x => `- ${x.id}${x.start ? ` (${x.start})` : ''}: ${x.result}. ${x.files.join(', ')}`),
    ...(a.provisional ? ['Pass grouping in this direction is provisional.'] : []),
    '',
    'Suggested checks:',
    ...a.checks.map(c => `- ${c}`),
    '',
    'A place worth inspecting, not a diagnosis of a broken rail. Sensor GPS cannot identify which track or rail was affected. An inspector confirms or dismisses the alert.'
  ].join('\n');
}

const lastSent = new Map();
let sentTimes = [];

const app = express();
app.disable('x-powered-by');
app.get(['/', '/index.html'], (req, res) => res.type('html').send(page));
app.get('/alert-rules.js', (req, res) => res.sendFile(path.join(__dirname, 'alert-rules.js')));
app.use('/data', express.static(path.join(__dirname, 'data')));
app.use('/figures', express.static(path.join(__dirname, 'figures')));

// Only the spot ID comes from the browser. The recipient and every number come from this server's data files.
app.post('/api/alert', express.json({ limit: '1kb' }), async (req, res) => {
  const spot = spots.get(req.body && req.body.id);
  if (!spot || level(spot.properties, alertRule) !== 'inspect') return res.status(400).json({ sent: false, reason: 'not an alertable spot' });
  if (!mailer) return res.json({ sent: false, reason: 'email not configured' });
  const now = Date.now();
  sentTimes = sentTimes.filter(t => now - t < 60 * 60 * 1000);
  if (now - (lastSent.get(spot.properties.id) || 0) < SPOT_COOLDOWN_MS || sentTimes.length >= MAX_PER_HOUR) return res.json({ sent: false, reason: 'rate limited' });
  lastSent.set(spot.properties.id, now);
  sentTimes.push(now);
  const alert = describe(spot, summary, recordings);
  try {
    // Some providers use a non-address SMTP username (SendGrid's is "apikey"); SMTP_FROM covers those.
    const from = process.env.SMTP_FROM || { name: 'Pinetrack alerts', address: SMTP_USER.includes('@') ? SMTP_USER : DEMO_ALERT_EMAIL };
    await mailer.sendMail({ from, to: DEMO_ALERT_EMAIL, subject: alert.subject, text: emailText(alert) });
    res.json({ sent: true });
  } catch (err) {
    console.error(`Alert email for ${alert.id} failed: ${err.message}`);
    res.json({ sent: false, reason: 'send failed' });
  }
});

// Malformed requests get a short JSON reply, never a stack trace.
app.use((err, req, res, next) => res.status(err.status || 500).json({ sent: false, reason: err.status < 500 ? 'bad request' : 'server error' }));

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Pinetrack demo running on port ${PORT}`);
  console.log(mailer ? `Alert emails go to ${DEMO_ALERT_EMAIL}` : `Alert emails are off (missing ${missing.join(', ')}); alerts stay on screen.`);
});
