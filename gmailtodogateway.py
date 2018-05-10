#!/usr/bin/env python

# Gmail monitoring service creating Todo items from emails with specific headline
# Code derived from :
# 	http://storiknow.com/automatic-cat-feeder-using-raspberry-pi-part-two/

import requests
import time
import os
import logging
import logging.handlers
import sys, traceback

from ConfigParser import SafeConfigParser
from imapclient import IMAPClient, SEEN

###########################
# PERSONAL CONFIG FILE READ
###########################

parser = SafeConfigParser()
parser.read('gmailtodogateway.ini')

# Read private developer for access to the google API
applicationCode = parser.get('config', 'applicationCode')

# Gmail account to monitor for todo emails
account = parser.get('config', 'account')

# Search pattern to look for in the header
pattern = parser.get('config', 'pattern')

# Read path to log file
LOG_FILENAME = parser.get('config', 'log_filename')

#################
#  LOGGING SETUP
#################
LOG_LEVEL = logging.INFO  # Could be e.g. "DEBUG" or "WARNING"

# Configure logging to log to a file, making a new file at midnight and keeping the last 3 day's data
# Give the logger a unique name (good practice)
logger = logging.getLogger(__name__)
# Set the log level to LOG_LEVEL
logger.setLevel(LOG_LEVEL)
# Make a handler that writes to a file, making a new file at midnight and keeping 3 backups
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when="midnight", backupCount=3)
# Format each log message like this
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
# Attach the formatter to the handler
handler.setFormatter(formatter)
# Attach the handler to the logger
logger.addHandler(handler)

# Make a class we can use to capture stdout and sterr in the log
class MyLogger(object):
	def __init__(self, logger, level):
		"""Needs a logger and a logger level."""
		self.logger = logger
		self.level = level

	def write(self, message):
		# Only log if there is a message (not just a new line)
		if message.rstrip() != "":
			self.logger.log(self.level, message.rstrip())

# Replace stdout with logging to file at INFO level
sys.stdout = MyLogger(logger, logging.INFO)
# Replace stderr with logging to file at ERROR level
sys.stderr = MyLogger(logger, logging.ERROR)

logger.info('Starting Gmail todo monitoring service')

SEEN_FLAG = 'SEEN'
UNSEEN_FLAG = 'UNSEEN'

 ##################
# MONITORING LOOP
##################
while True:

	try:

		logger.info("Checking gmail account for new todo items...")

		# Login
		server = IMAPClient('imap.gmail.com', use_uid=True, ssl=True)
		server.login(account, applicationCode)

		# Perform a search on the mail server for emails which header contains the pattern
		server.select_folder('INBOX')

		searchCriteria = [UNSEEN_FLAG, 'SUBJECT', pattern]

		# use this to get already read emails too
		#searchCriteria.append(SEEN_FLAG)

		ids = server.search(searchCriteria)

		if len(ids)==0:
			logger.info("No new action email found on server")

		# Get the emails matching the search
		for msgid, data in server.fetch(ids, ['ENVELOPE']).items():
			envelope = data[b'ENVELOPE']
			header = envelope.subject.decode()
		    
			logger.info("action to be added:[" +  header.replace(pattern, '', 1).lstrip().rstrip() + "], date="+ str(envelope.date))

			# Prepare and perform GET HTTP request to create a new item on the remote Todolist server
			GETdata={}
			GETdata["priority"] = "1"
			GETdata["creationdate"] = str(envelope.date)
			GETdata["newitem"] = header.replace(pattern, '', 1).lstrip().rstrip() 

			r = requests.get('http://192.168.0.13:8081/todolist_insert.php', params=GETdata)
			logger.info("HTTP request returned "+ r.text)
		 
		# mark the processed emails as read so as not to process them again next time
		server.select_folder('INBOX')
		server.set_flags(ids, [SEEN])

		# Logout from the server
		server.logout()
		logger.info('Logged out')

		# Poll account every 10 minutes
		time.sleep(600)

	except:
		logger.info("*****Exception in main loop, retrying in 30 seconds ******")
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=sys.stdout)	
		del exc_traceback
		time.sleep(30)
		continue
