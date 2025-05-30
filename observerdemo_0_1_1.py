#!/usr/bin/env python3

"""
A demo of the observer/subject pattern for log processing
"""

import asyncio
from typing import runtime_checkable, Any, List, Protocol

__author__ = "Joe Granville"
__date__ = "20250504"
__license__ = "MIT"
__version__ = "0.1.1"
__email__ = "jwgranville@gmail.com"
__status__ = "Proof-of-concept"


@runtime_checkable
class Observer(Protocol):
    """Observers can attach to and receive messages from Subjects"""

    async def update(self, message: Any) -> None:
        """Should handle updates from the Subject"""


class ObserverCallback(Protocol):
    """A function itself can respond to a Subject, without a class"""

    async def __call__(self, message: Any) -> None:
        """Like Observer.update, this should handle updates"""


@runtime_checkable
class Subject(Protocol):
    """
    Subjects should keep a subscriber list and broadcast notify to them
    """

    def attach(self, observer: Observer | ObserverCallback) -> None:
        """Should add an Observer to the subscriber list"""

    def detach(self, observer: Observer | ObserverCallback) -> None:
        """Should remove an Observer from the subscriber list"""

    async def notify(self, message: Any) -> None:
        """Should invoke the callback of every subscriber in the list"""


class SubjectMixin:
    """A mixable implementation of the Subject protocol"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes the _observers list of the SubjectMixin mixin"""
        super().__init__(*args, **kwargs)
        self._observers: List[ObserverCallback] = []

    def attach(self, observer: Observer | ObserverCallback) -> None:
        """
        Adds Observers to the _observers list

        If an Observer is not provided, we assume a Callable
        implementing ObserverCallback will be used in place of
        Observer.update.
        """
        if isinstance(observer, Observer):
            callback = observer.update
        else:
            callback = observer
        self._observers.append(callback)

    def detach(self, observer: Observer | ObserverCallback) -> None:
        """
        Removes Observers from the _observers list

        See also SubjectMixin.attach() regarding how ObserverCallback
        instances are handled.
        """
        if isinstance(observer, Observer):
            callback = observer.update
        else:
            callback = observer
        self._observers.remove(callback)

    async def notify(self, message: Any) -> None:
        """Invokes each callback in _observers"""
        asyncio.gather(
            callback(message) for callback in self._observers
        )


class SubjectProxy(SubjectMixin):
    """A means to create a Subject without mixing in to a base class"""
