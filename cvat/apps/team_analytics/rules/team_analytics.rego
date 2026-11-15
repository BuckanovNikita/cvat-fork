package team_analytics

import rego.v1

import data.utils
import data.organizations

# input: {
#     "scope": <"view"> or null,
#     "auth": {
#         "user": {
#             "id": <num>,
#             "privilege": <"admin"|"user"|"worker"> or null
#         },
#         "organization": {
#             "id": <num>,
#             "owner": {
#                 "id": <num>
#             },
#             "user": {
#                 "role": <"owner"|"maintainer"|"supervisor"|"worker"> or null
#             }
#         } or null,
#     },
#     "resource": null,
# }

default allow := false

allow if {
    utils.is_admin
}

# No global privilege floor: the organization role alone decides.
allow if {
    input.scope == utils.VIEW
    utils.is_organization
    organizations.has_perm(organizations.MAINTAINER)
}
