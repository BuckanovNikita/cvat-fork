package issues_comments_test

import rego.v1

# Run against the patched rules by default. Load {"expected":{"patched":false}}
# as an additional data file to verify the unmodified upstream baseline.
default patched := true

patched := data.expected.patched

resource := {
    "id": 10,
    "owner": {"id": 99},
    "assignee": {"id": 99},
    "project": {"owner": {"id": 99}, "assignee": {"id": 99}},
    "task": {"owner": {"id": 99}, "assignee": {"id": 99}},
    "job": {"assignee": {"id": 99}},
    "issue": {"owner": {"id": 99}, "assignee": {"id": 99}},
    "organization": {"id": 42},
}

request(role, scope) := {
    "scope": scope,
    "auth": {
        "user": {"id": 7, "privilege": "user"},
        "organization": {"id": 42, "owner": {"id": 99}, "user": {"role": role}},
        "organization_specified": true,
    },
    "resource": resource,
}

scopes := {
    "issues": ["create@job", "view", "update", "delete"],
    "comments": ["create@issue", "view", "update", "delete"],
}

organization_fields := {
    "issues": "job__segment__task__organization",
    "comments": "issue__job__segment__task__organization",
}

unrestricted(role) := true if {
    patched
} else := true if {
    role in {"maintainer", "owner"}
} else := false

test_unassigned_member_actions if {
    every package_name, package_scopes in scopes {
        every role in ["worker", "supervisor"] {
            every scope in package_scopes {
                result := data[package_name].allow with input as request(role, scope)
                result == patched
            }
        }
    }
}

test_senior_member_actions if {
    every package_name, package_scopes in scopes {
        every role in ["owner", "maintainer"] {
            every scope in package_scopes {
                data[package_name].allow with input as request(role, scope)
            }
        }
    }
}

test_nonmember_denied if {
    every package_name, package_scopes in scopes {
        every scope in array.concat(package_scopes, ["list"]) {
            not data[package_name].allow with input as request(null, scope)
        }
        not data[package_name].filter with input as request(null, "list")
    }
}

test_other_organization_denied if {
    every package_name, package_scopes in scopes {
        every role in ["worker", "supervisor", "maintainer", "owner"] {
            every scope in package_scopes {
                candidate := object.union(request(role, scope), {
                    "resource": object.union(resource, {"organization": {"id": 43}}),
                })
                not data[package_name].allow with input as candidate
            }
        }
    }
}

test_list_filter_contract if {
    every package_name, field in organization_fields {
        every role in ["worker", "supervisor", "maintainer", "owner"] {
            candidate := request(role, "list")
            data[package_name].allow with input as candidate
            result := data[package_name].filter with input as candidate
            result[0] == "&"
            result[2] == ["|", {field: 42}]
            result[3] == "org_filter_proof"
            count(result) == 4
            expected_unrestricted := unrestricted(role)
            actual_unrestricted := result[1] == {}
            actual_unrestricted == expected_unrestricted
        }
    }
}

test_sandbox_nonstaff_denied if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            not data[package_name].allow with input as candidate with input.auth.organization as null
        }
    }
}

test_sandbox_staff_retained if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            data[package_name].allow with input as candidate with input.auth.organization as null with input.resource.task.owner.id as 7
        }
    }
}

test_sandbox_filter_contract if {
    every package_name, field in organization_fields {
        candidate := request("worker", "list")
        explicit := data[package_name].filter with input as candidate with input.auth.organization as null
        explicit[0] == "&"
        explicit[1][0] == "|"
        explicit[2] == ["&", {field: null}]
        explicit[3] == "org_filter_proof"
        unspecified := data[package_name].filter with input as candidate with input.auth.organization as null with input.auth.organization_specified as false
        unspecified == ["&", explicit[1], "org_filter_proof"]
    }
}

test_admin_filter_scoped if {
    every package_name, field in organization_fields {
        candidate := request("worker", "list")
        result := data[package_name].filter with input as candidate with input.auth.user.privilege as "admin"
        result == ["&", {}, ["|", {field: 42}], "org_filter_proof"]
    }
}
