#!/usr/bin/env python3

"""
Count keystrokes as a proxy for many log processors run simultaneously

LineByLineTotalizer buffers incoming data until a newline character is
observed, similar to analyze.py used in previous versions; see
github.com/edurange/edurange3/scenarios/global_scripts/analyze.py.

There has previously been interest in the timing not just between
newlines, but all keystrokes. But analyze.py does not record this.
ImmediateTotalizer, FixedIntervalTotalizer and DynamicIntervalTotalizer
demonstrate alternative policies for how often to count and potentially
timestamp the contents of the input buffer.

These classes implement the Observer protocol (update()), allowing them
to respond to messages broadcast from Subject instances. See
observerdemo_0_1_1.py.

By broadcasting log events to all Observer instances, every log
processor can have equal access to the original log data without
resource conflicts or individual synchronization. See
toy_logger_tcp_0_1_3.py.
"""

from datetime import datetime
from math import exp
from time import perf_counter

from textbits import BOLD, FG_RED, RESET

__author__ = "Joe Granville"
__date__ = "20250513"
__license__ = "MIT"
__version__ = "0.1.1"
__email__ = "jwgranville@gmail.com"
__status__ = "Proof-of-concept"


class ImmediateTotalizer:
    """Counts time between updates and immediately totals data rate"""

    def __init__(self, outputq):
        """Create an ImmediateTotalizer that writes output to outputq"""
        self.outputq = outputq
        self.lastupdate = perf_counter()

    async def update(self, message):
        """Calculates rate based only on current message and timing"""
        currenttime = perf_counter()
        delta = currenttime - self.lastupdate
        self.lastupdate = currenttime
        numbytes = len(message)
        rate = numbytes / delta
        lt = ""
        plural = "s"
        if rate < 2:
            plural = ""
        if rate < 1:
            rate = 1
            lt = "<"
        await self.outputq.put(
            f"{FG_RED}[{datetime.now()}]{RESET} -- "
            f"{BOLD}ImmediateTotalizer{RESET} --\n"
            f"  {numbytes} characters in {delta:.3f} seconds: "
            f"{lt}{rate:.0f} character{plural} per second"
        )


class LineByLineTotalizer:
    """Counts time between lines; buffers until receiving a newline"""

    def __init__(self, outputq):
        """Create a LineByLineTotalizer that writes output to outputq"""
        self.outputq = outputq
        self.buffer = ""
        self.lastupdate = perf_counter()

    async def update(self, message):
        """Calculates rate based on the time since the last newline"""
        self.buffer = self.buffer + message
        if "\n" in self.buffer or "\r" in self.buffer:
            currenttime = perf_counter()
            delta = currenttime - self.lastupdate
            self.lastupdate = currenttime
            lines = self.buffer.splitlines(keepends=True)
            if "\n" not in lines[-1] and "\r" not in lines[-1]:
                self.buffer = lines[-1]
                lines = lines[:-1]
            numbytes = sum(len(line) for line in lines)
            rate = numbytes / delta
            lt = ""
            plural = "s"
            if rate < 2:
                plural = ""
            if rate < 1:
                rate = 1
                lt = "<"
            await self.outputq.put(
                f"{FG_RED}[{datetime.now()}]{RESET} -- "
                f"{BOLD}LineByLineTotalizer{RESET} --\n"
                f"  {numbytes} characters in {delta:.3f} seconds: "
                f"{lt}{rate:.0f} character{plural} per second"
            )


INTERVAL = 0.2


class FixedIntervalTotalizer:
    """Buffers data for a set amount of time before totaling"""

    def __init__(self, outputq, interval=INTERVAL):
        """Create a FixedIntervalTotalizer that writes to outputq"""
        self.outputq = outputq
        self.interval = interval
        self.buffer = ""
        self.lastupdate = perf_counter()

    async def update(self, message):
        """Calculates rate based on data since last interval"""
        currenttime = perf_counter()
        delta = currenttime - self.lastupdate
        self.buffer = self.buffer + message
        if delta > self.interval:
            self.lastupdate = currenttime
            numbytes = len(self.buffer)
            rate = numbytes / delta
            self.buffer = ""
            lt = ""
            plural = "s"
            if rate < 2:
                plural = ""
            if rate < 1:
                rate = 1
                lt = "<"
            await self.outputq.put(
                f"{FG_RED}[{datetime.now()}]{RESET} -- "
                f"{BOLD}FixedIntervalTotalizer{RESET} "
                f"({self.interval} seconds) --\n"
                f"  {numbytes} characters in {delta:.3f} seconds: "
                f"{lt}{rate:.0f} character{plural} per second"
            )


ALPHA = 0.1  # Exponential moving average rate
GAIN = 0.1  # Exponential decay gain rate
MIN_INTERVAL = 0.004  # 250 samples per second, 10x record typing speed
MAX_INTERVAL = 20.0  # 0.05 samples per second, 1/10 of hunt-and-peck
THETA = 0.1  # Exponential scaling slope
THRESHOLD = 0.2  # Rate change threshold? Might be derelict


class DynamicIntervalTotalizer:
    """
    Buffers data for a variable amount of time before totaling

    When the observed rate changes, the interval contracts to capture
    higher resolution. When the observed rate remains steady, the
    interval extends to count more events with relatively less log data.
    """

    def __init__(
        self,
        outputq,
        interval=INTERVAL,
        alpha=ALPHA,
        gain=GAIN,
        min_interval=MIN_INTERVAL,
        max_interval=MAX_INTERVAL,
        theta=THETA,
    ):
        """Create a DynamicIntervalTotalizer that writes to outputq"""
        self.outputq = outputq
        self.interval = interval
        self.alpha = alpha
        self.gain = gain
        self.max_interval = max_interval
        self.min_interval = min_interval
        self.theta = theta

        self.buffer = ""
        self.lastupdate = perf_counter()
        self.previousrate = 0.0

    async def update(self, message):
        """
        Calculates rate since last interval and adjusts interval

        The interval is adjusted according to the Exponential Moving
        Average of the observed data rate. A moving average is computed
        for the rates at every interval.
        """
        currenttime = perf_counter()
        delta = currenttime - self.lastupdate
        self.buffer = self.buffer + message
        if delta > self.interval:
            numbytes = len(self.buffer)
            rate = numbytes / delta
            self.buffer = ""

            smoothedrate = (
                self.alpha * rate + (1 - self.alpha) * self.previousrate
            )
            if smoothedrate:
                rate_ = abs(rate - smoothedrate) / smoothedrate
            else:
                rate_ = 0.0

            targetrate = (
                exp((0 - self.theta) * rate_)
                * self.max_interval
                / self.interval
            )
            self.interval = self.interval * (
                1 + (targetrate - 1) * self.gain
            )
            self.interval = max(
                self.min_interval, min(self.max_interval, self.interval)
            )

            self.previousrate = smoothedrate

            lt = ""
            plural = "s"
            if rate < 2:
                plural = ""
            if rate < 1:
                rate = 1
                lt = "<"
            await self.outputq.put(
                f"{FG_RED}[{datetime.now()}]{RESET} -- "
                f"{BOLD}DynamicIntervalTotalizer{RESET} "
                f"({self.interval:.3f} seconds) --\n"
                f"  {numbytes} characters in {delta:.3f} seconds: "
                f"{lt}{rate:.0f} character{plural} per second"
            )
            self.lastupdate = currenttime
