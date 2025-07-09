# demo-keystroke-observers

Demonstrates a one-writer-multiple-reader message topology for log processin.

## Instructions

To run it one can start:

 `./[toy_logger_tcp_0_1_3.py](https://github.com/edurange/demo-keystroke-observers/blob/main/toy_logger_tcp_0_1_3.py)`
 
Then, connect to local port 5554 and 5555 with a TTY utility such as [netcat](https://netcat.sourceforge.net):

 `nc 127.0.0.1 5554`
 
5554 mocks the behavior of ttylog and analyzes the input received. 5555 demonstrates that another interface, such as the guide or web GUI, could be simultaneously monitored and handled by different behavior.

## Explanation

This is a proposal for a new communication strategy in the log pipeline. This would exist in a place analogous to the space between [ttylog](https://github.com/edurange/edurange3/blob/main/scenarios/global_scripts/ttylog), [analyze.py](https://github.com/edurange/edurange3/blob/main/scenarios/global_scripts/analyze.py) and [milestone-lbl.pl](https://github.com/edurange/edurange3/blob/main/scenarios/global_scripts/milestone-lbl.pl) in the current implementation; see also [https://github.com/edurange/edurange3/tree/main/scenarios/global_scripts](https://github.com/edurange/edurange3/tree/main/scenarios/global_scripts).

LineByLineTotalizer buffers incoming data until a newline character is observed, similar to analyze.py used in previous versions. There has previously been interest in the timing not just between newlines, but all keystrokes. But analyze.py does not record this.

ImmediateTotalizer, FixedIntervalTotalizer and DynamicIntervalTotalizer demonstrate alternative policies for how often to count and potentially timestamp the contents of the input buffer. These classes implement the [Observer pattern](https://en.wikipedia.org/wiki/Observer_pattern) as a [Python protocol](https://typing.python.org/en/latest/spec/protocol.html) (`update()`), allowing them to respond to messages broadcast from Subject instances. See observerdemo_0_1_1.py.

By broadcasting log events to all Observer instances, every log processor can have equal access to the original log data without resource conflicts or individual synchronization. See toy_logger_tcp_0_1_3.py.

Rather than continue to modify and grow the features/responsibilities of analyze.py, I propose this method of creating a data pipeline that obeys the [Open-closed principle](https://en.wikipedia.org/wiki/Open–closed_principle), meaning that it is closed to code changes, but open to behavior extension by means of a pluggable interface; in this example, `Subject.attach()`. See observerdemo_0_1_1.py.
