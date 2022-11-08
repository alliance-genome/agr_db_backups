import logging

from .helper import APP_DESCRIPTION, APP_OPTIONS

import app

def lambda_handler(event, context):

	help_json = {
		"description": APP_DESCRIPTION+
		               " Send in a json payload with one or more of the below options as key-value pairs.",
		"options": APP_OPTIONS
	}

	if 'help' in event:
		logging.info(help_json)
		return help_json

	response_msg = app.main(event)

	return {
		'message' : response_msg
	}
