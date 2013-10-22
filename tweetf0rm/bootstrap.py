#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s-[%(module)s][%(funcName)s][%(lineno)d]: %(message)s')
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING)

import sys, time, argparse, json, os, pprint
sys.path.append(".")

import multiprocessing as mp
from tweetf0rm.exceptions import InvalidConfig
from tweetf0rm.redis_helper import NodeQueue, NodeCoordinator
from tweetf0rm.utils import full_stack, node_id, public_ip
from tweetf0rm.proxies import proxy_checker
from tweetf0rm.scheduler import Scheduler

def check_config(config):
	if ('apikeys' not in config or 'redis_config' not in config):
		raise InvalidConfig("something is wrong with your config file... you have to have redis_config and apikeys")

def start_server(config, proxies):
	import copy
	
	check_config(config)
	config = copy.copy(config)

	this_node_id = node_id()
	node_queue = NodeQueue(this_node_id, redis_config=config['redis_config'])
	node_queue.clear()

	scheduler = Scheduler(this_node_id, config=config, proxies=proxies)

	logger.info('starting node_id: %s'%this_node_id)

	node_coordinator = NodeCoordinator(config['redis_config'])
	#time.sleep(5)
	# the main event loop, actually we don't need one, since we can just join on the crawlers and don't stop until a terminate command to each crawler, but we need one to check on redis command queue ...
	
	pre_time = time.time()
	while True:
		# block, the main process...for a command
		if(not scheduler.is_alive()):
			logger.info("no crawler is alive... i'm done too...")
			break;

		cmd = node_queue.get(block=True, timeout=360)

		if cmd:
			scheduler.enqueue(cmd)
		
		if (time.time() - pre_time > 60):
			logger.info(pprint.pformat(scheduler.crawler_status()))
			#logger.info('local queue_sizes: %s'%scheduler.check_local_qsizes())
			pre_time = time.time()
			cmd = {'cmd': 'CRAWLER_FLUSH'}
			scheduler.enqueue(cmd)

	# cmd = {
	# 	"cmd": "CRAWL_FRIENDS",
	# 	"user_id": 1948122342,
	# 	"data_type": "ids",
	# 	"depth": 2,
	# 	"bucket":"friend_ids"
	# }
	# cmd = {
	# 	"cmd": "CRAWL_FRIENDS",
	# 	"user_id": 1948122342,
	# 	"data_type": "users",
	# 	"depth": 2,
	# 	"bucket":"friends"
	# }
	# # cmd = {
	# # 	"cmd": "CRAWL_USER_TIMELINE",
	# # 	"user_id": 1948122342#53039176,
	##	"bucket": "timelines"
	# # }


if __name__=="__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument('-c', '--config', help="config.json that contains a) twitter api keys; b) redis connection string;", required = True)
	parser.add_argument('-p', '--proxies', help="the proxies.json file")

	args = parser.parse_args()

	proxies = None
	if args.proxies:
		with open(os.path.abspath(args.proxies), 'rb') as proxy_f:
			proxies = json.load(proxy_f)['proxies']

	with open(os.path.abspath(args.config), 'rb') as config_f:
		config = json.load(config_f)	
		
		try:
			start_server(config, proxies)
		except KeyboardInterrupt:
			print()
			logger.error('You pressed Ctrl+C!')
			pass
		except Exception as exc:		
			logger.error(exc)
		finally:
			pass