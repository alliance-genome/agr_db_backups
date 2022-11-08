APP_DESCRIPTION = "This function can backup any AGR database or restore an earlier made"+\
                  " backup to the same or a different environment (e.g. for data roll-down)."

APP_OPTIONS = {
	"action":       "Define an action to perform. Value must be either 'backup' or 'restore'.",
	"db_host":      "Host URL of target DB. Defaults to AWS SSM parameter store value.",
	"db_name":      "DB name of target DB. Defaults to AWS SSM parameter store value.",
	"db_password":  "DB password for target DB. Defaults to AWS SSM parameter store value.",
	"db_user":      "DB username for target DB. Defaults to AWS SSM parameter store value.",
	"help":         "Print this help text (provide any value).",
	"identifier":   "Application identifier to backup/restore for (for example 'curation').",
	"loglevel":     "Set logging level. Must be one of DEBUG, INFO, WARNING, ERROR or CRITICAL.",
	"prod_restore": "Extra flag to prevent accidental restores to 'production' environments."+
					" Define this argument as 'true' to confirm intend to do a production environment restore.",
	"region":       "AWS region to retrieve/write backups from/to. Defaults to 'us-east-1'.",
	"s3_bucket":    "AWS S3 bucket name to retrieve/write backups from/to. Defaults to AWS SSM parameter store value.",
	"src_env":      "The source environment to find a backup from to restore."+
					" Defaults to 'production', only relevant for restore action.",
	"target_env":   "The target environment to backup/restore from/to. Defaults to 'dev'."
}

SSM_ARG_PARAMS = {       #key-value pairs matching {`input_param_name`: `ssm_param_key`}
	'db_host' :     'host',
	'db_name' :     'name',
	'db_user' :     'user',
	'db_password' : 'password',
	's3_bucket' :   'bucket'
};
