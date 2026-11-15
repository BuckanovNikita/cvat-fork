// Who is offered the Team Analytics header link: administrators only, while analytics is on.
const assert = require('node:assert/strict');
const test = require('node:test');
const { loadPage } = require('./helper.cjs');

const { canOpenTeamAnalytics } = loadPage('access.ts');

const cases = [
    // analytics enabled, groups, expected
    [true, ['admin'], true],
    [true, ['admin', 'user'], true],
    [true, ['user'], false],
    [true, ['business'], false],
    [true, ['worker'], false],
    [true, [], false],
    [false, ['admin'], false],
    [false, ['user'], false],
];

for (const [analyticsEnabled, groups, expected] of cases) {
    test(`${expected ? 'shows' : 'hides'} the link for groups ${groups.join('+') || 'none'}, analytics ${analyticsEnabled ? 'on' : 'off'}`, () => {
        assert.equal(canOpenTeamAnalytics({ analyticsEnabled, groups }), expected);
    });
}

test('a role in the current organization does not open it: an owner or maintainer gets no link', () => {
    for (const currentRole of ['owner', 'maintainer', 'supervisor', 'worker']) {
        assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: ['user'], currentRole }), false);
    }
    assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: ['admin'], currentRole: null }), true);
});

test('does not depend on the per-user Grafana access flag', () => {
    assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: ['admin'], hasAnalyticsAccess: false }), true);
    assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: ['user'], hasAnalyticsAccess: true }), false);
});

test('a user not yet loaded gets no link', () => {
    assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: undefined }), false);
    assert.equal(canOpenTeamAnalytics({ analyticsEnabled: true, groups: null }), false);
});
