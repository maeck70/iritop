#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
import argparse
import re
import os
import sys
import time
import json
import socket
from io import BytesIO
from datetime import timedelta
from multiprocessing.pool import ThreadPool


__VERSION__ = 0.1

"""
Simple Iota IRI Node Monitor

This is a simple monitor that runs from the command line.
Typically this is run on the IRI node itself, however,
as soon as the node is allowed to externally expose getNodeInfo and getNeighbors information,
then this tool can be run from a remote shell as well.
"""


try:
    import urllib2
except ImportError:
    sys.stderr.write("Missing python urllib2? Install via 'pip install urllib2'"
                     "\n")
    sys.exit(1)

try:
    from blessed import Terminal
except ImportError:
    sys.stderr.write("Missing python blessed package? Install via 'pip install"
                     " blessed'\n")
    sys.exit(1)

try:
    from urllib.parse import urlparse
except ImportError:
     from urlparse import urlparse


# Url request timeout
URL_TIMEOUT = 2

# Default node URL
NODE = "http://localhost:14265"

# Headers for HTTP call
HEADERS = {'Content-Type': 'application/json',
           'Accept-Charset': 'UTF-8',
           'X-IOTA-API-Version': '1'}

MB = 1024 * 1024


def parse_args():
    global NODE

    parser = argparse.ArgumentParser()

    parser.add_argument("-V", "--version", help="show program version",
                        action="store_true")

    parser.add_argument("-n", "--node", type=url,
                        help="set the node we are connecting with. Default: "
                             "%(default)s",
                        default=NODE)

    parser.add_argument("-p", "--poll-delay", type=int,
                        help="node poll delay. Default: %(default)s",
                        default=2)

    parser.add_argument("-b", "--blink-delay", type=float,
                        help="blink delay. Default: %(default)s",
                        default=0.5)

    return parser.parse_args()


def main():
    global NODE

    try:
        args = parse_args()
    except Exception as e:
        sys.stderr.write("Error parsing arguments: %s\n" % e)
        sys.exit(1)

    # check for --version or -V
    if args.version:
        print("this is IRITop version %s" % __VERSION__)
        sys.exit()   

    # Set to user provided node
    if args.node != NODE:
        NODE = args.node

    print("IRITop connecting to node %s..." % args.node)
    iri_top = IriTop(args)
    iri_top.run()


def url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ...or ipv6
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if regex.match(url):
        return url
    else:
        raise argparse.ArgumentTypeError("Invalid node URL")


def fetch_data(data):
    global NODE
    global HEADERS
    global URL_TIMEOUT

    try:
        request = urllib2.Request(url=NODE,
                                  data=data,
                                  headers=HEADERS)
    except Exception as e:
        sys.stderr.write("Fatal error: %s" % e)
        sys.exit(1)

    response = None
    try:
        response = urllib2.urlopen(request, timeout=URL_TIMEOUT)
    except urllib2.HTTPError as e:
        msg = e.read()
        return None, 'Request failed with code: %d, response: %s' % (e.code,
                                                                     msg)
    except urllib2.URLError as e:
        return None, 'Request failed'
    except socket.timeout as e:
        return None, 'Request timed out'
    except Exception as e:
        return None, 'Unknown error'

    return json.loads(response.read()), None


class IriTop:

    def __init__(self, args):
        self.term = Terminal()
        self.prev = {}
        self.poll_delay = args.poll_delay
        self.blink_delay = args.blink_delay
        self.commands = ["{'command': 'getNeighbors'}",
                         "{'command': 'getNodeInfo'}"]

    def run(self):         

        _ = os.system('clear')

        with self.term.cbreak():
	    val = ""
	    tlast = 0
            # history_index = 0
            # history_index_max = 3
            self.hist = {}
            # for a in range(history_index_max):
            #    hist.append({})

            while val.lower() != 'q':
                val = self.term.inkey(timeout=self.blink_delay)

                if int(time.time()) - tlast > self.poll_delay:

                    results = \
                        ThreadPool(len(self.commands)).imap_unordered(
                                                       fetch_data,
                                                       self.commands)

                    neighbors = None
                    node = None
                    for data, e in results:
                        if e is not None:
                            sys.stderr.write("Error fetching data from node:"
                                             " %s\n" % e)
                            time.sleep(2)
                            sys.exit(1)

                        if 'appName' in data.keys():
                            node = data
                        elif 'neighbors' in data.keys():
                            neighbors = data['neighbors']

                    tlast = int(time.time())

                    # Keep history of tx 
                    tx_history = {}
                    for neighbor in neighbors:
                        self.historizer('at',
                                        'numberOfAllTransactions',
                                        tx_history,
                                        neighbor)

                        self.historizer('nt',
                                        'numberOfNewTransactions',
                                        tx_history,
                                        neighbor)

                        self.historizer('st',
                                        'numberOfSentTransactions',
                                        tx_history,
                                        neighbor)

                        self.historizer('rt',
                                        'numberOfRandomTransactionRequests',
                                        tx_history,
                                        neighbor)

                        self.historizer('xt',
                                        'numberOfStaleTransactions',
                                        tx_history,
                                        neighbor)

                        self.historizer('it',
                                        'numberOfInvalidTransactions',
                                        tx_history,
                                        neighbor)

		    self.hist = tx_history

                height, width = self.term.height, self.term.width

                print(self.term.move(0, 0) + self.term.black_on_cyan(
                      "IRITop - Simple IOTA IRI Node Monitor".ljust(width)))

                self.show(1, 0, "appName", node, "appName")
                self.show(2, 0, "appVersion", node, "appVersion")

                self.show_string(1, 1, "jreMemory", "Free: %s Mb  Max: %s Mb "
                                 " Total: %s Mb" % 
                                 (node["jreFreeMemory"]//MB,
                                 node["jreMaxMemory"]//MB,
                                 node["jreTotalMemory"]//MB))

                self.show_histogram(2, 1, "jreMemory",
                                    node["jreTotalMemory"] - node["jreFreeMemory"],
                                    node["jreMaxMemory"],
                                    0.8,
                                    span=2)

                self.show(3, 0, "milestoneStart", node, "milestoneStartIndex")
                self.show(3, 1, "milestoneIndex", node, "latestMilestoneIndex")
                self.show(3, 2, "milestoneSolid", node,
                          "latestSolidSubtangleMilestoneIndex")

                self.show(4, 0, "jreVersion", node, "jreVersion")
                self.show(4, 1, "tips", node, "tips")
                self.show(4, 2, "txToRequest", node, "transactionsToRequest")

                self.show_string(5, 0, "Node Address", NODE)
                self.show(5, 2, "neighbors", node, "neighbors")

                self.show_neighbors(7, neighbors)

    def historizer(self, txtype, wsid, hd, n):
        nid = "%s-%s" % (n['address'], txtype)
        nidd = "%s-%sd" % (n['address'], txtype)
        c = n[wsid]
        try:
            p = self.hist[nid]
            hd[nid] = c
            if p > 0:
                hd[nidd] = c - p
            else:
                hd[nidd] = 0
        except KeyError:
            hd[nid] = 0
            hd[nidd] = 0

        n["%sDelta" % wsid] = hd[nidd]

    def show(self, row, col, label, dictionary, value):

        height, width = self.term.height, self.term.width

        x1 = (width // 3) * col
        x2 = x1 + 18

        vs = self.term.bright_cyan(str(dictionary[value]))

        # Highlight if no neighbors
        if value == "neighbors" and dictionary[value] == 0:
            vs = self.term.bright_red(str(dictionary[value]))

        # Highlight if latest milestone is out of sync with the solid milestone
        if value == "latestMilestoneIndex":
            diff = dictionary["latestSolidSubtangleMilestoneIndex"] - \
              dictionary["latestMilestoneIndex"]

            if diff != 0:
                if diff <= 2:
                    vs = self.term.bright_yellow(str(dictionary[value]))
                else:
                    vs = self.term.bright_red(str(dictionary[value]))

        if value in self.prev and dictionary[value] != self.prev[value]:
            vs = self.term.on_blue(vs)

        print(self.term.move(row, x1) + self.term.cyan(label + ":"))
        print(self.term.move(row, x2) + vs + "  ")

        self.prev[value] = dictionary[value]

    def show_string(self, row, col, label, value):

        height, width = self.term.height, self.term.width

        x1 = (width // 3) * col
        x2 = x1 + 18

        print(self.term.move(row, x1) + self.term.cyan(label + ":"))
        print(self.term.move(row, x2) +
              self.term.bright_cyan(str(value) + "  "))

    def show_histogram(self, row, col, label, value, value_max,
                       warning_limit=0.8, span=1):

        height, width = self.term.height, self.term.width

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

        print(self.term.move(row, x1) + self.term.cyan(label + ":"))
        print(self.term.move(row, x2)
              + self.term.white("[")
              + self.term.bright_green("|" * mG)
              + self.term.bright_yellow("|" * mY)
              + self.term.bright_red("|" * mR)
              + self.term.bright_black("|" * mB)
              + self.term.white("]"))

    def show_neighbors(self, row, neighbors):
        height, width = self.term.height, self.term.width
        cw = width // 9

        print(self.term.move(row, 0 * cw) + 
              self.term.black_on_green("Neighbor Address".ljust(cw*3)))
        print(self.term.move(row, 3 * cw) +
              self.term.black_on_green("All tx".rjust(cw)))
        print(self.term.move(row, 4 * cw) +
              self.term.black_on_green("New tx".rjust(cw)))
        print(self.term.move(row, 5 * cw) +
              self.term.black_on_green("Sent tx".rjust(cw)))
        print(self.term.move(row, 6 * cw) +
              self.term.black_on_green("Random tx".rjust(cw)))
        print(self.term.move(row, 7 * cw) +
              self.term.black_on_green("Invalid tx".rjust(cw)))
        print(self.term.move(row, 8 * cw) +
              self.term.black_on_green("Stale tx".rjust(cw)))

        row += 1
        for neighbor in neighbors:
            self.show_neighbor(row, neighbor, cw, height)
            row += 1

    def show_neighbor(self, row, neighbor, column_width, height):

        if row < height:

            addr = neighbor['connectionType'] + "://" + neighbor['address']
            at = "%d (%d)" % (neighbor['numberOfAllTransactions'],
                              neighbor['numberOfAllTransactionsDelta'])
            at = at.rjust(column_width)

            it = "%d (%d)" % (neighbor['numberOfInvalidTransactions'],
                              neighbor['numberOfInvalidTransactionsDelta'])
            it = it.rjust(column_width)

            nt = "%d (%d)" % (neighbor['numberOfNewTransactions'],
                              neighbor['numberOfNewTransactionsDelta'])
            nt = nt.rjust(column_width)

            rt = "%d (%d)" % (neighbor['numberOfRandomTransactionRequests'],
                              neighbor['numberOfRandomTransactionRequestsDelta'])
            rt = rt.rjust(column_width)

            st = "%d (%d)" % (neighbor['numberOfSentTransactions'],
                              neighbor['numberOfSentTransactionsDelta'])
            st = st.rjust(column_width)

            xt = "%d (%d)" % (neighbor['numberOfStaleTransactions'],
                              neighbor['numberOfStaleTransactionsDelta'])
            xt = xt.rjust(column_width)

            if (neighbor['numberOfAllTransactionsDelta'] == 0 and
              neighbor['numberOfAllTransactions'] > 0):
                addr = self.term.bright_red(addr)

            value_at = "neighbor-%s-at" % neighbor['address']
            if (value_at in self.prev and
              neighbor['numberOfAllTransactions'] != self.prev[value_at]):
                at = self.term.cyan(at)

            if neighbor['numberOfInvalidTransactions'] > 0:
                it = \
                    self.term.red(str(neighbor['numberOfInvalidTransactions'])
                             .rjust(column_width))

            value_it = "neighbor-%s-it" % neighbor['address']
            if (value_it in self.prev and
              neighbor['numberOfInvalidTransactions'] != self.prev[value_it]):
                it = self.term.cyan(it)

            value_nt = "neighbor-%s-nt" % neighbor['address']
            if (value_nt in self.prev and
              neighbor['numberOfNewTransactions'] != self.prev[value_nt]):
                nt = self.term.cyan(nt)

            value_rt = "neighbor-%s-rt" % neighbor['address']
            if (value_rt in self.prev and
              neighbor['numberOfRandomTransactionRequests'] != self.prev[value_rt]):
                rt = self.term.cyan(rt)

            value_st = "neighbor-%s-st" % neighbor['address']
            if (value_st in self.prev and
              neighbor['numberOfSentTransactions'] != self.prev[value_st]):
                st = self.term.cyan(st)

            if neighbor['numberOfStaleTransactions'] > 0:
                xt = self.term.yellow(xt)
            value_xt = "neighbor-%s-xt" % neighbor['address']
            if (value_xt in self.prev and
              neighbor['numberOfStaleTransactions'] != self.prev[value_xt]):
                xt = self.term.cyan(xt)

            print(self.term.move(row, 0 * column_width) + self.term.white(addr))
            print(self.term.move(row, 3 * column_width) + self.term.green(at))
            print(self.term.move(row, 4 * column_width) + self.term.green(nt))
            print(self.term.move(row, 5 * column_width) + self.term.green(st))
            print(self.term.move(row, 6 * column_width) + self.term.green(rt))
            print(self.term.move(row, 7 * column_width) + self.term.green(it))
            print(self.term.move(row, 8 * column_width) + self.term.green(xt))

            self.prev[value_at] = neighbor['numberOfAllTransactions']
            self.prev[value_it] = neighbor['numberOfInvalidTransactions']
            self.prev[value_nt] = neighbor['numberOfNewTransactions']
            self.prev[value_rt] = neighbor['numberOfRandomTransactionRequests']
            self.prev[value_st] = neighbor['numberOfSentTransactions']
            self.prev[value_xt] = neighbor['numberOfStaleTransactions']


if __name__ == '__main__':
    main()
