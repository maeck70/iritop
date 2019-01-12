#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
import argparse
import re
import sys
import time
import json
import yaml
from os import path
from curses import wrapper


__VERSION__ = '0.3.0'

"""\
Simple Iota IRI Node Monitor

This is a simple monitor that runs from the command line.
Typically this is run on the IRI node itself, however,
as soon as the node is allowed to externally expose
getNodeInfo and getNeighbors information, then this tool
can be run from a remote shell as well.

More information:
https://github.com/maeck70/iritop
"""


try:
    import urllib3
except ImportError:
    sys.stderr.write("Missing python urllib3? " +
                     "Install via 'pip install urllib3'"
                     "\n")
    sys.exit(1)

try:
    from blessed import Terminal
except ImportError:
    sys.stderr.write("Missing python blessed package? Install via 'pip install"
                     " blessed'\n")
    sys.exit(1)


# Url request timeout
URL_TIMEOUT = 5

# Default node URL
NODE = "http://localhost:14265"

# Headers for HTTP call
HEADERS = {'Content-Type': 'application/json',
           'Accept-Charset': 'UTF-8',
           'X-IOTA-API-Version': '1'}

BLINK_DELAY = 0.5
POLL_DELAY = 2
ITER = 0
MB = 1024 * 1024


def parse_args():
    global NODE
    global BLINK_DELAY
    global POLL_DELAY
    global URL_TIMEOUT

    parser = argparse.ArgumentParser(
        description='IRI Top status viewer',
        epilog='Configuration can also be set in yaml formatted file.'
               ' For the configuration keys omit prefix hyphen - or --, and'
               ' replace all other instances of - with _')

    parser.add_argument('--version', '-v', action='version',
                        version='iritop %s' % __VERSION__)

    parser.add_argument('-c', '--config', type=read_config,
                        help="configuration file. Defaults to ~/.iritop",
                        action=LoadFromFile)

    parser.add_argument("-n", "--node", type=url,
                        help="set the node we are connecting with. Default: " +
                              NODE)

    parser.add_argument("-p", "--poll-delay", type=int,
                        help="node poll delay. Default: %ss" % POLL_DELAY)

    parser.add_argument("-b", "--blink-delay", type=float,
                        help="blink delay. Default: %ss" % BLINK_DELAY)

    parser.add_argument("-t", "--url-timeout", type=int,
                        help="URL Timeout. Default: %ss" % URL_TIMEOUT)

    # Get configuration file if exists
    home_dir = path.expanduser("~")
    if path.isfile(home_dir + '/.iritop'):
        sys.argv.extend(['-c', home_dir + '/.iritop'])

    args = parser.parse_args()

    # Defaults not set by ArgumentParser so that they can
    # be overriden from command line (overrides file)
    if args.blink_delay is None:
        args.blink_delay = BLINK_DELAY
    if args.poll_delay is None:
        args.poll_delay = POLL_DELAY
    if args.node is not None:
        NODE = args.node

    return args


class LoadFromFile(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        for k, v in values.items():
            # Disallow pointing to another config
            if str(k) == 'c' or str(k) == 'config':
                continue

            # Don't override cli args
            if getattr(namespace, k) is not None:
                continue

            # Parse key values as arguments
            k = '--' + k.replace('_', '-')
            parser.parse_args((k, str(v)), namespace=namespace)


def main():
    try:
        args = parse_args()
    except Exception as e:
        sys.stderr.write("Error parsing arguments: %s\n" % e)
        sys.exit(1)

    iri_top = IriTop(args)
    wrapper(iri_top.run)


def url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if regex.match(url):
        return url
    else:
        raise argparse.ArgumentTypeError("Invalid node URL")


def read_config(config_file):
    with open(config_file) as fh:
        try:
            data = yaml.load(fh)
        except yaml.parser.ParserError as e:
            raise Exception("Error parsing yaml configuration file '%s': %s" %
                            (config_file, e))
        except Exception as e:
            raise Exception("Error reading configuration file '%s': %s" %
                            (config_file, e))
    return data


def fetch_data(data_to_send, method='POST'):
    global NODE
    global HEADERS
    global URL_TIMEOUT

    http = urllib3.PoolManager()

    try:
        data = json.dumps(data_to_send)
        response = http.request(method,
                                NODE,
                                body=data,
                                timeout=URL_TIMEOUT,
                                headers=HEADERS)
    except Exception as e:
        return None, 'Unknown error: %s' % e

    return json.loads(response.data.decode('utf-8')), None


class IriTop:

    def __init__(self, args):
        self.term = Terminal()
        self.prev = {}
        self.poll_delay = args.poll_delay
        self.blink_delay = args.blink_delay
        self.commands = [{'command': 'getNeighbors'},
                         {'command': 'getNodeInfo'}]
        self.txkeys = [{'keyshort': 'at',
                        'key': 'numberOfAllTransactions', 'col': 3},
                       {'keyshort': 'st',
                        'key': 'numberOfSentTransactions', 'col': 5},
                       {'keyshort': 'nt',
                        'key': 'numberOfNewTransactions', 'col': 4},
                       {'keyshort': 'rt',
                        'key': 'numberOfRandomTransactionRequests', 'col': 6},
                       {'keyshort': 'xt',
                        'key': 'numberOfStaleTransactions', 'col': 8},
                       {'keyshort': 'it',
                        'key': 'numberOfInvalidTransactions', 'col': 7}, ]
        self.baseline = dict()
        self.baselineStr = ['Off', 'On']
        self.baselineToggle = 0
        self.width = 0
        self.height = 0
        self.oldheight = 0
        self.oldwidth = 0 


    def run(self, stdscr):

        stdscr.clear()

        print("IRITop connecting to node %s..." % NODE)

        with self.term.cbreak():
            val = ""
            tlast = 0
            self.hist = {}

            while val.lower() != 'q':
                val = self.term.inkey(timeout=self.blink_delay)

                self.oldheight, self.oldwidth = self.height, self.width
                self.height, self.width = self.term.height, self.term.width

                if int(time.time()) - tlast > self.poll_delay:

                    results = [fetch_data(self.commands[i]) for i
                               in range(len(self.commands))]

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
                        for txkey in self.txkeys:
                            self.historizer(txkey['keyshort'],
                                            txkey['key'],
                                            tx_history,
                                            neighbor)

                    self.hist = tx_history

                if val.lower() == 'b':
                    for neighbor in neighbors:
                        for txkey in self.txkeys:
                            self.baseline[self.getBaselineKey(neighbor,
                                          txkey['keyshort'])] = \
                                          neighbor[txkey['key']]
                    self.baselineToggle = self.baselineToggle ^ 1

                if (self.oldheight != self.height) or (self.oldwidth != self.width):
                    print(self.term.clear)

                print(self.term.move(0, 0) + self.term.black_on_cyan(
                      "IRITop - Simple IOTA IRI Node Monitor"
                      .ljust(self.width)))

                for neighbor in neighbors:
                    for txkey in self.txkeys:
                        key = self.getBaselineKey(neighbor, txkey['keyshort'])
                        if key not in self.baseline:
                            self.baseline[key] = 0

                self.show(1, 0, "appName", node, "appName")
                self.show(2, 0, "appVersion", node, "appVersion")

                self.show_string(1, 1, "jreMemory", "Free: %s Mb  Max: %s Mb "
                                 " Total: %s Mb" %
                                 (node["jreFreeMemory"]//MB,
                                  node["jreMaxMemory"]//MB,
                                  node["jreTotalMemory"]//MB))

                self.show_histogram(2, 1, "jreMemory",
                                    node["jreTotalMemory"] -
                                    node["jreFreeMemory"],
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

                self.show_string(6, 0, "Baseline",
                                 self.baselineStr[self.baselineToggle])

                self.show_neighbors(7, neighbors)

    def getBaselineKey(self, neighbor, subkey):
        return "%s:%s" % (neighbor['address'], subkey)

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

        x1 = (self.width // 3) * col
        x2 = x1 + 18

        vs = self.term.bright_cyan(str(dictionary[value]))

        # Highlight if no neighbors
        if value == "neighbors" and dictionary[value] == 0:
            vs = self.term.bright_red(str(dictionary[value]))

        # Highlight if latest milestone is out of sync with the solid milestone
        if value == "latestSolidSubtangleMilestoneIndex":
            diff = dictionary["latestSolidSubtangleMilestoneIndex"] - \
              dictionary["latestMilestoneIndex"]

            if diff != 0:
                if diff <= 2:
                    vs = self.term.bright_yellow(str(dictionary[value]) + "*")
                else:
                    vs = self.term.bright_yellow_on_red(
                            str(dictionary[value]) + " (!)")

        if value in self.prev and dictionary[value] != self.prev[value]:
            vs = self.term.on_blue(vs)

        print(self.term.move(row, x1) + self.term.cyan(label + ":"))
        print(self.term.move(row, x2) + vs + "  ")

        self.prev[value] = dictionary[value]

    def show_string(self, row, col, label, value):

        x1 = (self.width // 3) * col
        x2 = x1 + 18

        print(self.term.move(row, x1) + self.term.cyan(label + ":"))
        print(self.term.move(row, x2) +
              self.term.bright_cyan(str(value) + "  "))

    def show_histogram(self, row, col, label, value, value_max,
                       warning_limit=0.8, span=1):

        label_width = 18
        col_width = ((self.width // 3) - label_width) + \
                    ((span - 1) * (self.width // 3))
        x1 = (self.width // 3) * col
        x2 = x1 + label_width
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
              + self.term.bright_red("+" * mR)
              + self.term.bright_black("-" * mB)
              + self.term.white("]"))

    def show_neighbors(self, row, neighbors):
        global ITER
        cols = 9
        height, width = self.term.height, self.term.width
        cw = width // cols
        cw1 = width - ((cols - 1) * cw)
        cwl = [0, ]
        for c in range(cols - 1):
            cwl.append(cw1 + (c * cw))

        print(self.term.move(row, cwl[0]) +
              self.term.black_on_green("Neighbor Address".ljust(cw*4)))
        print(self.term.move(row, cwl[3]) +
              self.term.black_on_green("All tx".rjust(cw)))
        print(self.term.move(row, cwl[4]) +
              self.term.black_on_green("New tx".rjust(cw)))
        print(self.term.move(row, cwl[5]) +
              self.term.black_on_green("Sent tx".rjust(cw)))
        print(self.term.move(row, cwl[6]) +
              self.term.black_on_green("Random tx".rjust(cw)))
        print(self.term.move(row, cwl[7]) +
              self.term.black_on_green("Invalid tx".rjust(cw)))
        print(self.term.move(row, cwl[8]) +
              self.term.black_on_green("Stale tx".rjust(cw)))

        row += 1
        for neighbor in neighbors:
            self.show_neighbor(row, neighbor, cwl, cw, height)
            row += 1

        print(self.term.move(height - 2, 0 * cw) +
              self.term.black_on_cyan(
                    "Press Q to exit - "
                    "Press B to reset tx to a zero baseline".ljust(width)))

        ITER += 1

    def txString(self, neighbor, key, keydelta, keyshort, column_width):
        txcnt = neighbor[key] - (self.baseline[self.getBaselineKey(neighbor,
                                 keyshort)] * self.baselineToggle)
        return ("%d (%d)" % (txcnt, neighbor[keydelta])).rjust(column_width)

    def show_neighbor(self, row, neighbor, column_start_list,
                      column_width, height):
        global ITER

        neighbor['addr'] = neighbor['connectionType'] + \
            "://" + neighbor['address']

        # Create display string
        for txkey in self.txkeys:
            neighbor[txkey['keyshort']] = \
                    self.txString(neighbor,
                                  txkey['key'],
                                  '%sDelta' % txkey['key'],
                                  txkey['keyshort'],
                                  column_width)

        # Highlight neighbors that are incommunicade
        if (neighbor['numberOfAllTransactionsDelta'] == 0 and ITER > 12):
            neighbor['addr'] = self.term.bright_red("(!) " + neighbor['addr'])

        value_at = "neighbor-%s-at" % neighbor['address']
        if (value_at in self.prev and
                neighbor['numberOfAllTransactions'] != self.prev[value_at]):
            neighbor['at'] = self.term.cyan(neighbor['at'])

        if neighbor['numberOfInvalidTransactions'] > 0:
            neighbor['it'] = \
                self.term.red(str(neighbor['numberOfInvalidTransactions'])
                              .rjust(column_width))

        # Blink changed value
        for txkey in self.txkeys:
            neighborkey = "neighbor-%s-%s" % (neighbor['address'],
                                              txkey['keyshort'])
            if (neighborkey in self.prev and
                    neighbor[txkey['key']] != self.prev[neighborkey]):
                neighbor[txkey['keyshort']] = \
                    self.term.cyan(neighbor[txkey['keyshort']])

        # do not display any neighbors crossing the height of the terminal
        if row < height - 2:
            print(self.term.move(row, column_start_list[0]) +
                  self.term.white(neighbor['addr'] + "    "))
            for txkey in self.txkeys:
                print(self.term.move(row, column_start_list[txkey['col']]) +
                      self.term.green(neighbor[txkey['keyshort']]))

        # Store previous value
        for txkey in self.txkeys:
            neighborkey = "neighbor-%s-%s" % (neighbor['address'],
                                              txkey['keyshort'])
            self.prev[neighborkey] = neighbor[txkey['key']]


if __name__ == '__main__':
    main()
