// Seam 2: the events the UI logging sends, at the boundary to the server.
// Run after installing cvat's dependencies: node --test verify/team_analytics_logging.cjs
// Each topic is one file under verify/team-analytics-logging/ (`*.test.cjs`), sharing helper.cjs.
const { readdirSync } = require('node:fs');
const path = require('node:path');

const directory = path.join(__dirname, 'team-analytics-logging');
for (const file of readdirSync(directory).filter((name) => name.endsWith('.test.cjs')).sort()) {
    require(path.join(directory, file));
}
