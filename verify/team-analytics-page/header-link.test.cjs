// Who is offered the Team Analytics header link.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage } = require('./helper.cjs');

const { canOpenTeamAnalytics } = loadPage('access.ts');

const cases = [
    // analytics enabled, groups, role in the current organization, expected
    [true, ['user'], 'owner', true],
    [true, ['user'], 'maintainer', true],
    [true, ['admin'], null, true],
    [true, ['admin', 'user'], 'worker', true],
    [true, ['user'], 'supervisor', false],
    [true, ['user'], 'worker', false],
    [true, ['user'], null, false],
    [true, [], null, false],
    [false, ['admin'], 'owner', false],
    [false, ['user'], 'maintainer', false],
];

for (const [analyticsEnabled, groups, currentRole, expected] of cases) {
    test(`${expected ? 'shows' : 'hides'} the link for groups ${groups.join('+') || 'none'}, role ${currentRole}, analytics ${analyticsEnabled ? 'on' : 'off'}`, () => {
        assert.equal(canOpenTeamAnalytics({ analyticsEnabled, groups, currentRole }), expected);
    });
}

test('does not depend on the per-user Grafana access flag', () => {
    assert.equal(canOpenTeamAnalytics({
        analyticsEnabled: true, groups: ['user'], currentRole: 'maintainer', hasAnalyticsAccess: false,
    }), true);
    assert.equal(canOpenTeamAnalytics({
        analyticsEnabled: true, groups: ['user'], currentRole: 'worker', hasAnalyticsAccess: true,
    }), false);
});

test('a user not yet loaded gets no link', () => {
    assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: undefined, currentRole: null }), false);
});
