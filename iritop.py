#!/usr/bin/python3

from __future__ import division
from blessed import Terminal

import argparse
import time
import json
import pycurl
from io import BytesIO
from urllib.parse import urlencode
from datetime import timedelta


prev = {}
poll_delay = 2
blink_delay = 0.5

def show(row, col, label, dictionary, value):

	height, width = term.height, term.width

	x1 = (width // 3) * col
	x2 = x1 + 18

	vs = term.bright_cyan(str(dictionary[value]))

	# Highlight if no neighbors 
	if value == "neighbors" and dictionary[value] == 0:
		vs = term.bright_red(str(dictionary[value]))
	
	# Highlight if latest milestone is out of sync with the solid milestone
	if value == "latestMilestoneIndex":
		diff = dictionary["latestSolidSubtangleMilestoneIndex"] - dictionary["latestMilestoneIndex"]
		if diff != 0:
			if diff <= 2:
				vs = term.bright_yellow(str(dictionary[value]))
			else:
				vs = term.bright_red(str(dictionary[value]))

	if value in prev and dictionary[value] != prev[value]:
		vs = term.on_blue(vs)

	print(term.move(row, x1) + term.cyan(label + ":"))
	print(term.move(row, x2) + vs + "  ")

	prev[value] = dictionary[value]


def show_string(row, col, label, value):

	height, width = term.height, term.width

	x1 = (width // 3) * col
	x2 = x1 + 18

	print(term.move(row, x1) + term.cyan(label + ":"))
	print(term.move(row, x2) + term.bright_cyan(str(value) + "  "))

	
def show_histogram(row, col, label, value, value_max, warning_limit = 0.8, span = 1):
	
	height, width = term.height, term.width

	label_width = 18
	col_width = ((width // 3) - label_width) + ((span - 1) * (width // 3))
	x1 = (width // 3) * col
	x2 = x1 + label_width
	b1 = x2 + 1
	bw = col_width - 2

	vm = bw
	v = int(value / value_max * bw)
	vl = int(warning_limit * vm)

	mG = v
	mY = 0
	mR = 0
	if v > vl:
		mR = v - vl
		mG = mG - mR
	mB = bw - (mR + mG)
	if value > (value_max * warning_limit):
		mY = mG
		mG = 0

	print(term.move(row, x1) + term.cyan(label + ":"))
	print(term.move(row, x2)
			+ term.white("[") 
			+ term.bright_green("|" * mG) 
			+ term.bright_yellow("|" * mY) 
			+ term.bright_red("|" * mR) 
			+ term.bright_black("|" * mB) 
			+ term.white("]"))


def show_neighbors(row):
		height, width = term.height, term.width
		cw = width // 9

		print(term.move(row, 0 * cw) + term.black_on_green("Neighbor Address".ljust(cw*3)))
		print(term.move(row, 3 * cw) + term.black_on_green("All tx".rjust(cw)))
		print(term.move(row, 4 * cw) + term.black_on_green("Invalid tx".rjust(cw)))
		print(term.move(row, 5 * cw) + term.black_on_green("New tx".rjust(cw)))
		print(term.move(row, 6 * cw) + term.black_on_green("Random tx".rjust(cw)))
		print(term.move(row, 7 * cw) + term.black_on_green("Sent tx".rjust(cw)))
		print(term.move(row, 8 * cw) + term.black_on_green("Stale tx".rjust(cw)))

		row += 1
		for n in neighbors['neighbors']:
			show_neighbor(row, n, cw, height)
			row += 1



def show_neighbor(row, neighbor, column_width, height):

	if row < height:
		at = str(neighbor['numberOfAllTransactions']).rjust(column_width)
		atd = str(neighbor['numberOfAllTransactionsDelta']).rjust(column_width)

		at = "%d (%d)" % (neighbor['numberOfAllTransactions'], neighbor['numberOfAllTransactionsDelta'])
		at = at.rjust(column_width)
		it = str(neighbor['numberOfInvalidTransactions']).rjust(column_width)
		nt = str(neighbor['numberOfNewTransactions']).rjust(column_width)
		rt = str(neighbor['numberOfRandomTransactionRequests']).rjust(column_width) 
		st = str(neighbor['numberOfSentTransactions']).rjust(column_width)
		xt = str(neighbor['numberOfStaleTransactions']).rjust(column_width)

		value_at = "neighbor-%s-at"  % neighbor['address']
		if value_at in prev and neighbor['numberOfAllTransactions'] != prev[value_at]:
			at = term.cyan(at)

		if neighbor['numberOfInvalidTransactions'] > 0:
			it = term.red(str(neighbor['numberOfInvalidTransactions']).rjust(column_width)) 
		value_it = "neighbor-%s-it"  % neighbor['address']
		if value_it in prev and neighbor['numberOfInvalidTransactions'] != prev[value_it]:
			it = term.cyan(it)

		value_nt = "neighbor-%s-nt"  % neighbor['address']
		if value_nt in prev and neighbor['numberOfNewTransactions'] != prev[value_nt]:
			nt = term.cyan(nt)

		value_rt = "neighbor-%s-rt"  % neighbor['address']
		if value_rt in prev and neighbor['numberOfRandomTransactionRequests'] != prev[value_rt]:
			rt = term.cyan(rt)

		value_st = "neighbor-%s-st"  % neighbor['address']
		if value_st in prev and neighbor['numberOfSentTransactions'] != prev[value_st]:
			st = term.cyan(st)

		if neighbor['numberOfStaleTransactions'] > 0:
			xt = term.yellow(str(neighbor['numberOfStaleTransactions']).rjust(column_width)) 
		value_xt = "neighbor-%s-xt"  % neighbor['address']
		if value_xt in prev and neighbor['numberOfStaleTransactions'] != prev[value_xt]:
			xt = term.cyan(xt)

		print(term.move(row, 0 * column_width) + term.white(neighbor['connectionType'] + " " + neighbor['address']))
		print(term.move(row, 3 * column_width) + term.green(at))
		print(term.move(row, 4 * column_width) + term.green(it))
		print(term.move(row, 5 * column_width) + term.green(nt))
		print(term.move(row, 6 * column_width) + term.green(rt))
		print(term.move(row, 7 * column_width) + term.green(st))
		print(term.move(row, 8 * column_width) + term.green(xt))

		prev[value_at] = neighbor['numberOfAllTransactions']
		prev[value_it] = neighbor['numberOfInvalidTransactions']
		prev[value_nt] = neighbor['numberOfNewTransactions']
		prev[value_rt] = neighbor['numberOfRandomTransactionRequests']
		prev[value_st] = neighbor['numberOfSentTransactions']
		prev[value_xt] = neighbor['numberOfStaleTransactions']



# initiate the parser
parser = argparse.ArgumentParser()  
parser.add_argument("-V", "--version", help="show program version", action="store_true")
parser.add_argument("-n", "--node", help="set the node we are connecting with", default="http://localhost:14265")

# read arguments from the command line
args = parser.parse_args()

# check for --version or -V
if args.version:  
    print("this is IRITop version 0.1")


print("IRITop connection to node %s..." % args.node)

term = Terminal()
with term.fullscreen():

	val = ""
	tlast = 0
	# history_index = 0
	# history_index_max = 3
	hist = {}
	# for a in range(history_index_max):
	# 	hist.append({})

	while val.lower() != 'q':


		if int(time.time()) - tlast > poll_delay:

			# --- getNodeInfo
			buffer = BytesIO()
			c = pycurl.Curl()
			c.setopt(c.URL, args.node)
			c.setopt(c.WRITEDATA, buffer)
			c.setopt(c.HTTPHEADER, ['Content-Type: application/json','Accept-Charset: UTF-8', 'X-IOTA-API-Version: 1'])
			c.setopt(c.POSTFIELDS, "{'command': 'getNodeInfo'}")
			c.perform()
			c.close()

			body = buffer.getvalue().decode('utf-8')
			node = json.loads(body)

			tlast = int(time.time())

			# --- getNeighbors
			buffer = BytesIO()
			c = pycurl.Curl()
			c.setopt(c.URL, args.node)
			c.setopt(c.WRITEDATA, buffer)
			c.setopt(c.HTTPHEADER, ['Content-Type: application/json','Accept-Charset: UTF-8', 'X-IOTA-API-Version: 1'])
			c.setopt(c.POSTFIELDS, "{'command': 'getNeighbors'}")
			c.perform()
			c.close()

			body = buffer.getvalue().decode('utf-8')
			neighbors = json.loads(body)

			# Keep history of tx 
			hd = {}
			for n in neighbors['neighbors']:
				nid = "%s-at" % n['address']
				nidd = "%s-atd" % n['address']
				atc = n['numberOfAllTransactions']
				try:
					atp = hist[nid]
					hd[nid] = atc
					if atp > 0:
						hd[nidd] = atc - atp
					else:
						hd[nidd] = 0
				except KeyError:
					atp = 0
					hd[nid] = 0
					hd[nidd] = 0
				n['numberOfAllTransactionsDelta'] = hd[nidd]
			hist = hd

		mb = 1024*1024
		height, width = term.height, term.width

		print(term.move(0, 0) + term.black_on_cyan("IRITop - Simple IOTA IRI Node Monitor".ljust(width)))

		show(1, 0, "appName", node, "appName")
		show(2, 0, "appVersion", node, "appVersion")

		show_string(1, 1, "jreMemory", "Free: %s Mb  Max: %s Mb  Total: %s Mb" % (node["jreFreeMemory"]//mb, node["jreMaxMemory"]//mb, node["jreTotalMemory"]//mb))
		show_histogram(2, 1, "jreMemory", node["jreTotalMemory"] - node["jreFreeMemory"], node["jreMaxMemory"], 0.8, span = 2)

		show(3, 0, "milestoneStart", node, "milestoneStartIndex")
		show(3, 1, "milestoneIndex", node, "latestMilestoneIndex")
		show(3, 2, "milestoneSolid", node, "latestSolidSubtangleMilestoneIndex")

		show(4, 0, "jreVersion", node, "jreVersion")
		show(4, 1, "tips", node, "tips")
		show(4, 2, "txToRequest", node, "transactionsToRequest")

		show_string(5, 0, "Node Address", args.node)
		show(5, 2, "neighbors", node, "neighbors")

		show_neighbors(7)

		val = term.inkey(timeout = blink_delay)

