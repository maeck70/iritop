# iritop
##Simple Iota IRI Node Monitor

This is a simple monitor that runs from the command line. Typically this is run on the IRI node itself, however, as soon as the node is allowed to externally expose getNodeInfo and getNeighbors information, then this tool can be run from a remote shell as well.

The primary motivation to build this tool for me was to have a way of continously monitoring my Iota IRI nodes using a lightweight tool that can be run on both the server terminal and from a remote command line.

The Monitoring tool will show basic information on the node like version, milestone information and jre memory usage. It will also show the details of the neighbors connected to the node. Transaction counts are shown for Total, New, Random, Sent and Invalid transactions.

Where possible, the tool will highlight where the statistics are outside the norm by highlighting in yellow or red.

![IRITopScreenshot](https://raw.githubusercontent.com/maeck70/iritop/master/img/IRITop.png)

##Usage:
- Start without a --node argument will assume 'http://localhost:14265' as the node address for the web service calls.
- Provide an address using --node http://myirinode:14265 if you want to specify a specific address.

##Arguments:
>  -h, --help            show this help message and exit
>  -v, --version         show program's version number and exit
>  -c CONFIG, --config CONFIG
>                        configuration file. Defaults to ~/.iritop
>  -n NODE, --node NODE  set the node we are connecting with. Default:
>                        http://localhost:14265
>  -p POLL_DELAY, --poll-delay POLL_DELAY
>                        node poll delay. Default: 2s
>  -b BLINK_DELAY, --blink-delay BLINK_DELAY
>                        blink delay. Default: 0.5s

The configuration can also be set in yaml formatted file. By default the configuration file from ~/.iritop is read. All configuration parameters can be provided in the config file. 

##Example:
`node: http://mynode.com:14265`


Use 'q' to exit from the tool.

##Prerequisites:
- Python 2 or 3
- Urllib2 (pip install urllib2)
- Blessed (pip install blessed)
