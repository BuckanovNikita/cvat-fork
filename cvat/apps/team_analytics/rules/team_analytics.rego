package team_analytics

import rego.v1

import data.utils

# Team Analytics (its figures and its settings) is read and changed by administrators only, with or
# without an organization selected. No organization role allows it, an owner's included.
#
# input: {
#     "scope": <"view"|"update"> or null,
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
