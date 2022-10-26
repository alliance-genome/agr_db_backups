from optparse import OptionParser

from .helper import APP_OPTIONS

import app

def cli_handler():
	parser = OptionParser()
	for arg_key, arg_value in APP_OPTIONS.items():
		if arg_key == 'help':
			continue
		parser.add_option('--'+arg_key, help=arg_value)

	(options, args) = parser.parse_args()

	response_msg = app.main(vars(options))
	print(response_msg)
