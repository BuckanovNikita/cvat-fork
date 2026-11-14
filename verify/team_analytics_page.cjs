// Seam 3: the Team Analytics page against supplied service responses.
// Run after installing cvat's dependencies and the harness's own (npm ci --prefix verify):
//   node --test verify/team_analytics_page.cjs
// Without the harness's dependencies the suite fails and names what is missing (browser-environment.cjs).
// Each topic is one file under verify/team-analytics-page/ (`*.test.cjs`), sharing helper.cjs.
const { readdirSync } = require('node:fs');
const path = require('node:path');

const directory = path.join(__dirname, 'team-analytics-page');
for (const file of readdirSync(directory).filter((name) => name.endsWith('.test.cjs')).sort()) {
    require(path.join(directory, file));
}
