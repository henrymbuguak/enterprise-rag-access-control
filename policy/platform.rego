package main

import rego.v1

# docker-compose.yml: every image pinned to a tag, never :latest
deny contains msg if {
	some name, svc in input.services
	endswith(svc.image, ":latest")
	msg := sprintf("service %s uses an unpinned ':latest' image", [name])
}

deny contains msg if {
	some name, svc in input.services
	svc.image
	not contains(svc.image, ":")
	msg := sprintf("service %s has no image tag", [name])
}

# tools.json: no tool may run as a service account
deny contains msg if {
	is_array(input)
	some tool in input
	tool.auth_mode != "user"
	msg := sprintf("tool %s must run with auth_mode=user", [tool.name])
}

deny contains msg if {
	is_array(input)
	some tool in input
	not tool.auth_mode
	msg := sprintf("tool %s is missing auth_mode", [tool.name])
}
