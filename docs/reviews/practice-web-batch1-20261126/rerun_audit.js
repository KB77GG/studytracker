// Run the preserved Claude probes with explicit local port/output/browser paths.
// Original sources remain byte-identical to 54078056 for comparison.
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const [name, port, output] = process.argv.slice(2);
if (!['crawl', 'flows', 'dialog', 'probe', 'probe2'].includes(name) || !/^\d{4,5}$/.test(port || '') || !output) {
  throw new Error('Usage: node rerun_audit.js <probe> <local port> <output directory>');
}
const sourcePath = path.resolve(__dirname, '../practice-web-audit-20261126', name + '.js');
const out = path.resolve(output);
fs.mkdirSync(path.join(out, 'shots'), { recursive: true });
let source = fs.readFileSync(sourcePath, 'utf8')
  .replaceAll('http://127.0.0.1:5055', 'http://127.0.0.1:' + port)
  .replaceAll("__dirname + '/out'", JSON.stringify(out))
  .replaceAll('chromium.launch()', 'chromium.launch({ executablePath: process.env.AUDIT_CHROMIUM || undefined })');
// Make failures finite and observable, especially controls deliberately removed.
source = 'process.on("unhandledRejection", e => { console.error(e); process.exit(1); });\n' + source;
const loaded = new Module(sourcePath, module);
loaded.filename = sourcePath;
loaded.paths = Module._nodeModulePaths(path.dirname(sourcePath));
loaded._compile(source, sourcePath);
