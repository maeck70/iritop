# iritop
Simple Iota IRI Node Monitor

This is a simple monitor that runs from the commandline. Typically this is run on the IRI node itself.However, as soon as the node is allowed to externally expose getNodeInfo and getNeighbors information, then this tool can be run from a remote shell as well.

The Monitoring tool will show basic information on the node like version, milestone information and jre memory usage. It will also show the details of the neighbors connected to the node. Transaction counts are shown for Total, New, Random, Sent and Invalid transactions.

Where possible, the toolwill highlight where the statistics are outside the norm by highlighting in yellow or red.

![IRITopScreenshot](maeck70.github.com/iritop/img/IRITop.png)

Usage:
- Start without a --node argument will assume 'http://localhost:14265' as the node address for the web service calls.
- Provide an address using --node http://myirinode:14265 if you want to specify a specific address.

Use 'q' enter to exit from the tool.

Prerequisites:
- Python3
- Blessed (pip install blessed)
