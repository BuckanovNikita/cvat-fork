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
                every privilege in ["user", "worker"] {
                    result := data[package_name].allow with input as request(role, scope) with input.auth.user.privilege as privilege
                    result == patched
                }
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

# The same two contracts for a caller whose global role is `worker`, the floor
# itself. Stock gives such a caller the staff filter even as an organization
# maintainer or owner, because stock's unrestricted branch needs the `user` role.
test_other_organization_denied_global_worker if {
    every package_name, package_scopes in scopes {
        every role in ["worker", "supervisor", "maintainer", "owner"] {
            every scope in package_scopes {
                candidate := object.union(request(role, scope), {
                    "resource": object.union(resource, {"organization": {"id": 43}}),
                })
                not data[package_name].allow with input as candidate with input.auth.user.privilege as "worker"
            }
        }
    }
}

test_list_filter_contract_global_worker if {
    every package_name, field in organization_fields {
        every role in ["worker", "supervisor", "maintainer", "owner"] {
            candidate := request(role, "list")
            data[package_name].allow with input as candidate with input.auth.user.privilege as "worker"
            result := data[package_name].filter with input as candidate with input.auth.user.privilege as "worker"
            result[0] == "&"
            result[2] == ["|", {field: 42}]
            result[3] == "org_filter_proof"
            count(result) == 4
            expected := {true: {}, false: staff_filters[package_name]}[patched]
            result[1] == expected
        }
    }
}

test_sandbox_nonstaff_denied if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            not data[package_name].allow with input as candidate with input.auth.organization as null with input.resource.organization as null
        }
    }
}

test_sandbox_staff_retained if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            data[package_name].allow with input as candidate with input.auth.organization as null with input.resource.organization as null with input.resource.task.owner.id as 7
        }
    }
}

test_removed_member_staff_denied if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request(null, scope)
            every privilege in ["user", "worker"] {
                not data[package_name].allow with input as candidate with input.auth.user.privilege as privilege with input.resource.task.owner.id as 7
            }
        }
    }
}

test_sandbox_context_cannot_access_organization_resource if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            every privilege in ["user", "worker"] {
                not data[package_name].allow with input as candidate with input.auth.user.privilege as privilege with input.auth.organization as null with input.resource.task.owner.id as 7
            }
        }
    }
}

test_organization_context_cannot_access_sandbox_resource if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            every privilege in ["user", "worker"] {
                not data[package_name].allow with input as candidate with input.auth.user.privilege as privilege with input.resource.organization as null with input.resource.task.owner.id as 7
            }
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

# A caller with no global role (privilege null) is below the patch's floor: the
# patched policies must decide exactly as stock for every action and for the list
# filter. The expectations below are stock's results, written out, and do not
# depend on `patched`, so the same cases pass on the stock tag and on the patched
# tree. Stock lets such a caller view what it is staff of and list its own items.

organization_roles := ["worker", "supervisor", "maintainer", "owner"]

staff_filters := {
    "issues": ["|",
        {"owner": 7},
        {"assignee": 7},
        {"job__assignee": 7},
        {"job__segment__task__owner": 7},
        {"job__segment__task__assignee": 7},
        {"job__segment__task__project__owner": 7},
        {"job__segment__task__project__assignee": 7},
    ],
    "comments": ["|",
        {"owner": 7},
        {"issue__owner": 7},
        {"issue__assignee": 7},
        {"issue__job__assignee": 7},
        {"issue__job__segment__task__owner": 7},
        {"issue__job__segment__task__assignee": 7},
        {"issue__job__segment__task__project__owner": 7},
        {"issue__job__segment__task__project__assignee": 7},
    ],
}

test_no_global_role_staff_gets_stock_actions if {
    every package_name, package_scopes in scopes {
        every role in organization_roles {
            every scope in package_scopes {
                result := data[package_name].allow with input as request(role, scope) with input.auth.user.privilege as null with input.resource.job.assignee.id as 7
                result == (scope == "view")
            }
        }
    }
}

test_no_global_role_nonstaff_gets_stock_actions if {
    every package_name, package_scopes in scopes {
        every role in organization_roles {
            every scope in package_scopes {
                not data[package_name].allow with input as request(role, scope) with input.auth.user.privilege as null
            }
        }
    }
}

test_no_global_role_member_gets_stock_list_filter if {
    every package_name, field in organization_fields {
        every role in organization_roles {
            every staff_id in [7, 99] {
                candidate := request(role, "list")
                data[package_name].allow with input as candidate with input.auth.user.privilege as null with input.resource.job.assignee.id as staff_id
                result := data[package_name].filter with input as candidate with input.auth.user.privilege as null with input.resource.job.assignee.id as staff_id
                result == ["&", staff_filters[package_name], ["|", {field: 42}], "org_filter_proof"]
            }
        }
    }
}

test_no_global_role_sandbox_gets_stock_actions if {
    every package_name, package_scopes in scopes {
        every scope in package_scopes {
            candidate := request("worker", scope)
            staff := data[package_name].allow with input as candidate with input.auth.user.privilege as null with input.auth.organization as null with input.resource.organization as null with input.resource.job.assignee.id as 7
            staff == (scope == "view")
            not data[package_name].allow with input as candidate with input.auth.user.privilege as null with input.auth.organization as null with input.resource.organization as null
        }
    }
}

test_no_global_role_nonmember_gets_stock_actions if {
    every package_name, package_scopes in scopes {
        every scope in array.concat(package_scopes, ["list"]) {
            not data[package_name].allow with input as request(null, scope) with input.auth.user.privilege as null with input.resource.job.assignee.id as 7
        }
        not data[package_name].filter with input as request(null, "list") with input.auth.user.privilege as null
    }
}

# A global role that is missing from the input or unknown to the helpers is below
# the floor as well, and gets the stock decisions too. The caller is made staff
# through two different fields: the job assignee and the task owner.

staff_paths := ["/resource/job/assignee/id", "/resource/task/owner/id"]

below_floor_request(kind, role, scope) := json.patch(request(role, scope), [{"op": "replace", "path": "/auth/user/privilege", "value": null}]) if {
    kind == "null"
}

below_floor_request(kind, role, scope) := json.remove(request(role, scope), ["auth/user/privilege"]) if {
    kind == "missing"
}

below_floor_request(kind, role, scope) := json.patch(request(role, scope), [{"op": "replace", "path": "/auth/user/privilege", "value": "superuser"}]) if {
    kind == "unknown"
}

as_staff(candidate, path) := json.patch(candidate, [{"op": "replace", "path": path, "value": 7}])

staff_actions_are_stock(kind, paths) if {
    every package_name, package_scopes in scopes {
        every role in organization_roles {
            every path in paths {
                every scope in package_scopes {
                    candidate := as_staff(below_floor_request(kind, role, scope), path)
                    result := data[package_name].allow with input as candidate
                    result == (scope == "view")
                }
            }
        }
    }
}

nonstaff_actions_are_stock(kind) if {
    every package_name, package_scopes in scopes {
        every role in organization_roles {
            every scope in package_scopes {
                not data[package_name].allow with input as below_floor_request(kind, role, scope)
            }
        }
    }
}

list_filter_is_stock(kind, paths) if {
    every package_name, field in organization_fields {
        every role in organization_roles {
            every path in paths {
                candidate := as_staff(below_floor_request(kind, role, "list"), path)
                data[package_name].allow with input as candidate
                result := data[package_name].filter with input as candidate
                result == ["&", staff_filters[package_name], ["|", {field: 42}], "org_filter_proof"]
            }
        }
    }
}

test_no_global_role_task_owner_gets_stock_actions if {
    staff_actions_are_stock("null", ["/resource/task/owner/id"])
}

test_no_global_role_task_owner_gets_stock_list_filter if {
    list_filter_is_stock("null", ["/resource/task/owner/id"])
}

test_missing_global_role_staff_gets_stock_actions if {
    staff_actions_are_stock("missing", staff_paths)
}

test_missing_global_role_nonstaff_gets_stock_actions if {
    nonstaff_actions_are_stock("missing")
}

test_missing_global_role_member_gets_stock_list_filter if {
    list_filter_is_stock("missing", staff_paths)
}

test_unknown_global_role_staff_gets_stock_actions if {
    staff_actions_are_stock("unknown", staff_paths)
}

test_unknown_global_role_nonstaff_gets_stock_actions if {
    nonstaff_actions_are_stock("unknown")
}

test_unknown_global_role_member_gets_stock_list_filter if {
    list_filter_is_stock("unknown", staff_paths)
}

test_admin_filter_scoped if {
    every package_name, field in organization_fields {
        candidate := request("worker", "list")
        result := data[package_name].filter with input as candidate with input.auth.user.privilege as "admin"
        result == ["&", {}, ["|", {field: 42}], "org_filter_proof"]
    }
}
