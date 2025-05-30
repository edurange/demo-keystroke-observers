#!/usr/bin/env python3

"""A multichannel log demo using TCP sockets as proxies for snooped TTY

This is a proposal for a new communication strategy in the log pipeline.
This would exist in a place analogous to the space between ttylog,
analyze.py and milestone-lbl.pl in the current implementation; see also
github.com/edurange/edurange3/scenarios/global_scripts/.

After starting this script on the command line, use a utility such as
netcat to connect to ports 5554 and 5555. 5554 mocks the behavior of
ttylog and analyzes the input received. 5555 demonstrates that another
interface, such as the guide or web GUI, could be simultaneously
monitored and handled by different behavior.

Rather than continue to modify and grow the features/responsibilities of
analyze.py, I propose this method of creating a data pipeline that obeys
the Open-Closed Principle, meaning that it is closed to code changes,
but open to behavior extension by means of a pluggable interface; in
this example, Observer.attach(). See observerdemo_0_1_1.py.

In a full scale version, Subjects could potentially be stored in a
dictionary so that Observers could find and attach to them by keyword,
and this might also be exposed as part of the pluggable interface.
"""

import asyncio
from datetime import datetime

from keystrokeanalysis_0_1_1 import (
    ImmediateTotalizer,
    LineByLineTotalizer,
    FixedIntervalTotalizer,
    DynamicIntervalTotalizer,
)
from observerdemo_0_1_1 import SubjectProxy
from textbits import BOLD, FG_BLUE, FG_GREEN, FG_RED, RESET

__author__ = "Joe Granville"
__date__ = "20250513"
__license__ = "MIT"
__version__ = "0.1.3"
__email__ = "jwgranville@gmail.com"
__status__ = "Proof-of-concept"


CHUNK_SIZE = 4096
HOST_IP = "127.0.0.1"
STDIO_PORT = 5554
GUIDE_PORT = 5555
LOG_PATH = "log.txt"


def toystdioserver(subject, logqueue):
    """
    Captures subject and logqueue in a closure for a TCP handler

    subject is a Subject to broadcast to using Subject.notify(). All
    attached Observers will receive messages containing data read from
    the port this server monitors.

    logqueue is an asyncio.Queue used to spool writes to a shared log
    output.
    """

    async def stdiohandler(reader, writer):
        """
        Logs and passes TCP activity to the message broadcasting Subject

        The buffer is echoed back to the user to indicate that the
        server is actively processing input.
        """
        name = BOLD + toystdioserver.__name__ + RESET
        addr = writer.get_extra_info("peername")
        addrstr = f"{addr[0]}:{addr[1]}"
        await writeto(logqueue, f"{name}: {addrstr} connected")
        while data := await reader.read(CHUNK_SIZE):  # Catch exceptions
            message = data.decode()
            messagestr = f"{BOLD}{FG_BLUE}{message!r}{RESET}"
            await writeto(
                logqueue,
                f"{name}: received {messagestr} from {addrstr}",
            )

            await subject.notify(message)

            writer.write(data)  # Echo
            await writer.drain()
        await writeto(logqueue, f"{name}: {addrstr} closed connection")
        writer.close()

    return stdiohandler


def toyguideserver(subject, logqueue):
    """
    Captures subject and logqueue in a closure for a TCP handler

    See also toystdiosterver.
    """

    async def guidehandler(reader, writer):
        """
        Logs and passes TCP activity to the message broadcasting Subject

        The buffer is echoed back to the user. But unlike the
        stdiohandler in toyguideserver, this data goes to a different
        Subject and is not processed by the totalizers.

        This is to demonstrate that multiple types of data sources can
        be processed simultaneously within the same log processor. In a
        more elaborate demonstration, the mock guide and stdio data
        sources would generate different types of log events, and all
        types of events would be equally available for processing by all
        log Observers.
        """
        name = BOLD + toyguideserver.__name__ + RESET
        addr = writer.get_extra_info("peername")
        addrstr = f"{addr[0]}:{addr[1]}"
        await writeto(logqueue, f"{name}: {addrstr} connected")
        while data := await reader.read(CHUNK_SIZE):  # Catch exceptions
            message = data.decode()
            messagestr = f"{BOLD}{FG_GREEN}{message!r}{RESET}"
            await writeto(
                logqueue,
                f"{name}: received {messagestr} from {addrstr}",
            )

            await subject.notify(message)

            writer.write(data)  # Echo
            await writer.drain()
        await writeto(logqueue, f"{name}: {addrstr} closed connection")
        writer.close()

    return guidehandler


async def startserver(factory, host, port, subject, logqueue):
    """Opens a TCP port using the handler returned by factory"""
    name = BOLD + startserver.__name__ + RESET
    factoryname = BOLD + factory.__name__ + RESET
    server = await asyncio.start_server(
        factory(subject, logqueue), host, port
    )
    async with server:
        await writeto(
            logqueue,
            f'{name}: "{factoryname}" started on {host}:{port}',
        )
        await server.serve_forever()


async def writeto(queue, message):
    """Wraps asyncio.Queue.put and adds a timestamp"""
    logstr = f"{FG_RED}[{datetime.now()}]{RESET} {message}"
    await queue.put(logstr)


async def spoollogfrom(queue, filename):
    """Reads a queue and writes to a file on behalf of all loggers"""
    with open(filename, "a", encoding="utf-8") as logfile:
        print("Spooling...")
        while message := await queue.get():  # Catch exceptions here
            print(message)
            logfile.write(message + "\n")
            logfile.flush()
            queue.task_done()


def subjectserver(serverfactory, host, port, logqueue):
    """Creates a subject and server task given a server factory"""
    subject = SubjectProxy()
    server = startserver(serverfactory, host, port, subject, logqueue)
    task = asyncio.create_task(server)
    return subject, task


async def starttasks():
    """Set up and run the async tasks for the Observer/Totalizer demo"""
    logqueue = asyncio.Queue()
    spooltask = asyncio.create_task(spoollogfrom(logqueue, LOG_PATH))

    stdiosubject, stdiotask = subjectserver(
        toystdioserver, HOST_IP, STDIO_PORT, logqueue
    )

    _, guidetask = subjectserver(
        toyguideserver, HOST_IP, GUIDE_PORT, logqueue
    )

    tasks = [spooltask, stdiotask, guidetask]

    totalizers = [
        ImmediateTotalizer(logqueue),
        LineByLineTotalizer(logqueue),
        FixedIntervalTotalizer(logqueue),
        DynamicIntervalTotalizer(logqueue),
    ]

    for totalizer in totalizers:
        stdiosubject.attach(totalizer)

    await asyncio.gather(*tasks)  # Catch exceptions here


if __name__ == "__main__":
    asyncio.run(starttasks())  # Catch exceptions here
