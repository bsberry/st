#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import can
import epyq.pyqabstractitemmodel
import functools
import serial.tools.list_ports
import sys
import time

from collections import OrderedDict
from epyq.abstractcolumns import AbstractColumns
from epyq.treenode import TreeNode
from PyQt5.QtCore import (Qt, QVariant, QModelIndex, pyqtSignal, pyqtSlot,
                          QPersistentModelIndex)
from PyQt5.QtWidgets import QFileDialog

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class Columns(AbstractColumns):
    _members = ['name', 'bitrate', 'transmit']

Columns.indexes = Columns.indexes()

def available_buses():
    valid = []

    for interface in can.interface.VALID_INTERFACES:
        if interface == 'pcan':
            for n in range(1, 9):
                channel = 'PCAN_USBBUS{}'.format(n)
                try:
                    bus = can.interface.Bus(bustype=interface, channel=channel)
                except:
                    pass
                else:
                    bus.shutdown()
                    valid.append({'type': CanBus,
                                  'device': [interface, channel]})
        elif interface == 'socketcan':
            for n in range(9):
                channel = 'can{}'.format(n)
                try:
                    bus = can.interface.Bus(bustype=interface, channel=channel)
                except:
                    pass
                else:
                    bus.shutdown()
                    valid.append({'type': CanBus,
                                  'device': [interface, channel]})
            for n in range(9):
                channel = 'vcan{}'.format(n)
                try:
                    bus = can.interface.Bus(bustype=interface, channel=channel)
                except:
                    pass
                else:
                    bus.shutdown()
                    valid.append({'type': CanBus,
                                  'device': [interface, channel]})
        else:
            print('Availability check not implemented for {}'
                  .format(interface), file=sys.stderr)


    for port in sorted(serial.tools.list_ports.comports()):
        valid.append({'type': SunspecBus,
                      'device': [port.device]})

    return valid


class Bus(TreeNode):
    def __init__(self, device, type_string):
        TreeNode.__init__(self)

        self.device = device
        self.type_string = type_string

        self.bitrate = self.default_bitrate
        self.separator = ' - '

        if self.device is not None:
            name = self.separator.join(self.device)
        else:
            name = 'Offline ({})'.format(self.type_string)

        self.fields = Columns(name=name,
                              bitrate=self.bitrates[self.default_bitrate],
                              transmit='')

        self._checked = Columns.fill(Qt.Unchecked)

    def set_data(self, data):
        for key, value in bitrates.items():
            if data == value:
                self.bitrate = key
                self.fields.bitrate = data

                self.set_bus()

        raise ValueError('{} not found in {}'.format(
            data,
            ', '.join(bitrates.values())
        ))

    def enumeration_strings(self):
        return bitrates.values()

    def unique(self):
        if self.device is not None:
            return self.separator.join(self.device)

        return None

    def append_child(self, child):
        TreeNode.append_child(self, child)

    def checked(self, column):
        return self._checked[column]

    def set_checked(self, checked, column):
        if column in [Columns.indexes.name, Columns.indexes.transmit]:
            if self.interface is None:
                self._checked[column] = Qt.Unchecked

                return

            self._checked[column] = checked

            if self._checked[column] == Qt.Checked:
                for device in self.children:
                    if device.checked(column) != Qt.Unchecked:
                        device.set_checked(checked=Qt.Checked,
                                           column=column)
            elif self._checked[column] == Qt.Unchecked:
                for device in self.children:
                    if device.checked(column) != Qt.Unchecked:
                        device.set_checked(checked=Qt.PartiallyChecked,
                                           column=column)

            if column == Columns.indexes.name:
                self.set_bus()
            elif column == Columns.indexes.transmit:
                self.bus.transmit = checked == Qt.Checked

    def set_bus(self):
        if self.device == None:
            return

        self.bus.set_bus(None)

        if self._checked.name == Qt.Checked:
            real_bus = self.construct_real_bus()
        else:
            real_bus = None

        self.bus.set_bus(bus=real_bus)


class SunspecBus(Bus):
    bitrates = OrderedDict([
        (9600, '9600 Bit/s')
    ])

    default_bitrate = 9600

    def __init__(self, device):
        Bus.__init__(self, device=device, type_string='SunSpec')

        self.bus = epyq.busproxy.BusProxy(
            transmit=self.checked(Columns.indexes.transmit))


class CanBus(Bus):
    bitrates = OrderedDict([
        (1000000, '1 MBit/s'),
        (500000, '500 kBit/s'),
        (250000, '250 kBit/s'),
        (125000, '125 kBit/s')
    ])

    default_bitrate = 500000

    def __init__(self, device):
        Bus.__init__(self, device=device, type_string='CAN')

        if self.device is not None:
            self.interface = self.device.pop(0)
            self.channel = self.device.pop(0)
            if len(device) > 0:
                raise Exception('Extra device parameters passed: {}'.format(device))

        self.bus = epyq.busproxy.BusProxy(
            transmit=self.checked(Columns.indexes.transmit))

    def construct_real_bus(self):
        real_bus = can.interface.Bus(bustype=self.interface,
                                     channel=self.channel,
                                     bitrate=self.bitrate)
        # TODO: Yuck, but it helps recover after connecting to a bus with
        #       the wrong speed.  So, find a better way.
        time.sleep(0.5)

        return real_bus


class Device(TreeNode):
    def __init__(self, device):
        TreeNode.__init__(self)

        self.fields = Columns(name=device.name,
                              bitrate='',
                              transmit='')

        self._checked = Columns.fill(Qt.Unchecked)

        self.device = device
        self.device.bus.transmit = self._checked.transmit == Qt.Checked

    def unique(self):
        return self.device

    def checked(self, column):
        return self._checked[column]

    def set_checked(self, checked, column):
        if column in [Columns.indexes.name, Columns.indexes.transmit]:
            if checked == Qt.Checked:
                if self.tree_parent.checked(column) == Qt.Checked:
                    self._checked[column] = Qt.Checked
                else:
                    if self._checked[column] == Qt.Unchecked:
                        self._checked[column] = Qt.PartiallyChecked
                    else:
                        self._checked[column] = Qt.Unchecked
            elif checked == Qt.PartiallyChecked:
                self._checked[column] = Qt.PartiallyChecked
            else:
                self._checked[column] = Qt.Unchecked

            self.device.bus_status_changed(
                online=self._checked.name == Qt.Checked,
                transmit=self._checked.transmit == Qt.Checked)

            if column == Columns.indexes.name:
                if self._checked[column] == Qt.Unchecked:
                    self.device.bus.set_bus()
                else:
                    self.device.bus.set_bus(self.tree_parent.bus)

            elif column == Columns.indexes.transmit:
                self.device.bus.transmit = self._checked[column] == Qt.Checked


class Tree(TreeNode):
    def __init__(self):
        TreeNode.__init__(self)


class Model(epyq.pyqabstractitemmodel.PyQAbstractItemModel):
    device_removed = pyqtSignal(epyq.device.Device)

    def __init__(self, root, parent=None):
        buses = (
            [
                {'type': CanBus, 'device': None},
                {'type': SunspecBus, 'device': None}
            ]
            + available_buses()
        )
        for bus in buses:
            parameters = set(bus.keys())
            parameters.discard('type')
            parameters = {name: bus[name] for name in parameters}

            constructor = bus['type']
            bus = constructor(**parameters)
            root.append_child(bus)
            went_offline = functools.partial(self.went_offline, node=bus)
            bus.bus.went_offline.connect(went_offline)

        editable_columns = Columns.fill(False)
        editable_columns.bitrate = True

        checkbox_columns = Columns.fill(False)
        checkbox_columns.name = True
        checkbox_columns.transmit = True

        epyq.pyqabstractitemmodel.PyQAbstractItemModel.__init__(
                self, root=root, editable_columns=editable_columns,
                checkbox_columns=checkbox_columns, parent=parent)

        self.headers = Columns(name='Name',
                               bitrate='Bitrate',
                               transmit='Transmit')

    def went_offline(self, node):
        # TODO: trigger gui update, or find a way that does it automatically
        node.set_checked(checked=Qt.Unchecked,
                         column=Columns.indexes.name)
        self.changed(node, Columns.indexes.name,
                     node, Columns.indexes.name,
                     [Qt.CheckStateRole])

    def setData(self, index, data, role=None):
        if index.column() == Columns.indexes.bitrate:
            if role == Qt.EditRole:
                node = self.node_from_index(index)
                try:
                    node.set_data(data)
                except ValueError:
                    return False
                self.dataChanged.emit(index, index)
                return True
        elif index.column() in [Columns.indexes.name, Columns.indexes.transmit]:
            if role == Qt.CheckStateRole:
                node = self.node_from_index(index)

                node.set_checked(checked=data, column=index.column())

                # TODO: CAMPid 9349911217316754793971391349
                children = len(node.children)
                if children > 0:
                    self.changed(node.children[0], Columns.indexes[0],
                                 node.children[-1], Columns.indexes[-1],
                                 [Qt.CheckStateRole])

                return True

        return False

    def add_device(self, bus, device):
        index = len(bus.children)

        # TODO: move to TreeNode?
        self.begin_insert_rows(bus, index, index)
        bus.append_child(device)
        self.end_insert_rows()

        persistent_index = QPersistentModelIndex(self.index_from_node(bus))
        self.layoutChanged.emit([persistent_index])

    def remove_device(self, device):
        bus = device.tree_parent
        row = bus.children.index(device)

        self.begin_remove_rows(bus, row, row)
        bus.remove_child(row)
        self.end_remove_rows()

        persistent_index = QPersistentModelIndex(self.index_from_node(bus))
        self.layoutChanged.emit([persistent_index])

        # TODO: This reset should not be needed but I have been unable
        #       so far to resolve them otherwise.  Since this doesn't
        #       happen much the performance cost is low but it does
        #       collapse the entire tree...
        self.beginResetModel()
        self.endResetModel()

        self.device_removed.emit(device.device)

if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
