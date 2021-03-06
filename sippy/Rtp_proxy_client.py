# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2009 Sippy Software, Inc. All rights reserved.
#
# This file is part of SIPPY, a free RFC3261 SIP stack and B2BUA.
#
# SIPPY is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# For a license to use the SIPPY software under conditions
# other than those described here, or to purchase support for this
# software, please contact Sippy Software, Inc. by e-mail at the
# following addresses: sales@sippysoft.com.
#
# SIPPY is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

from Timeout import Timeout
from Rtp_proxy_client_udp import Rtp_proxy_client_udp
from Rtp_proxy_client_local import Rtp_proxy_client_local

from time import time
from hashlib import md5
from random import random

class Rtp_proxy_client(Rtp_proxy_client_udp, Rtp_proxy_client_local):
    worker = None
    address = None
    online = False
    copy_supported = False
    stat_supported = False
    tnot_supported = False
    sbind_supported = False
    shutdown = False
    proxy_address = None
    caps_done = False
    sessions_created = None
    active_sessions = None
    active_streams = None
    preceived = None
    ptransmitted = None

    def __init__(self, global_config, *address):
        #print 'Rtp_proxy_client', address
        if len(address) > 0 and type(address[0]) in (tuple, list):
            Rtp_proxy_client_udp.__init__(self, global_config, *address)
        else:            
            Rtp_proxy_client_local.__init__(self, global_config, *address)
        self.version_check()

    def send_command(self, *args, **kwargs):
        if self.is_local:
            Rtp_proxy_client_local.send_command(self, *args, **kwargs)
        else:
            Rtp_proxy_client_udp.send_command(self, *args, **kwargs)

    def caps_query1(self, result):
        #print '%s.caps_query1(%s)' % (id(self), result)
        if self.shutdown:
            if self.worker != None:
                self.worker.shutdown()
                self.worker = None
            return
        if not self.online:
            return
        if result != '1':
            if result != None:
                self.copy_supported = False
                self.stat_supported = False
                self.tnot_supported = False
                self.sbind_supported = False
                self.caps_done = True
            return
        self.copy_supported = True
        self.send_command('VF 20080403', self.caps_query2)

    def caps_query2(self, result):
        #print '%s.caps_query2(%s)' % (id(self), result)
        if self.shutdown:
            if self.worker != None:
                self.worker.shutdown()
                self.worker = None
            return
        if not self.online:
            return
        if result != None:
            if result == '1':
                self.stat_supported = True
                self.send_command('VF 20081224', self.caps_query3)
                return
            else:
                self.stat_supported = False
                self.tnot_supported = False
                self.sbind_supported = False
                self.caps_done = True

    def caps_query3(self, result):
        #print '%s.caps_query3(%s)' % (id(self), result)
        if self.shutdown:
            if self.worker != None:
                self.worker.shutdown()
                self.worker = None
            return
        if not self.online:
            return
        if result != None:
            if result == '1':
                self.tnot_supported = True
            else:
                self.tnot_supported = False
            self.send_command('VF 20090810', self.caps_query4)
            return

    def caps_query4(self, result):
        #print '%s.caps_query4(%s)' % (id(self), result)
        if self.shutdown:
            if self.worker != None:
                self.worker.shutdown()
                self.worker = None
            return
        if not self.online:
            return
        if result != None:
            if result == '1':
                self.sbind_supported = True
            else:
                self.sbind_supported = False
            self.caps_done = True

    def version_check(self):
        self.send_command('V', self.version_check_reply)

    def version_check_reply(self, version):
        if self.shutdown:
            if self.worker != None:
                self.worker.shutdown()
                self.worker = None
            return
        if version == '20040107':
            self.go_online()
        elif self.online:
            self.go_offline()
        else:
            Timeout(self.version_check, 60)

    def heartbeat(self):
        #print 'heartbeat', self, self.address
        self.send_command('Ib', self.heartbeat_reply)

    def heartbeat_reply(self, stats):
        #print 'heartbeat_reply', self.address, stats, self.online
        if self.shutdown:
            if self.worker != None:
                self.worker.shutdown()
                self.worker = None
            return
        if not self.online:
            return
        if stats == None:
            self.active_sessions = None
            self.go_offline()
        else:
            sessions_created = active_sessions = active_streams = preceived = ptransmitted = 0
            for line in stats.splitlines():
                line_parts = line.split(':', 1)
                if line_parts[0] == 'sessions created':
                    sessions_created = int(line_parts[1])
                elif line_parts[0] == 'active sessions':
                    active_sessions = int(line_parts[1])
                elif line_parts[0] == 'active streams':
                    active_streams = int(line_parts[1])
                elif line_parts[0] == 'packets received':
                    preceived = int(line_parts[1])
                elif line_parts[0] == 'packets transmitted':
                    ptransmitted = int(line_parts[1])
                self.update_active(active_sessions, sessions_created, active_streams, preceived, ptransmitted)
        Timeout(self.heartbeat, 10)

    def go_online(self):
        if not self.online:
            self.caps_done = False
            self.send_command('VF 20071218', self.caps_query1)
            self.online = True
            self.heartbeat()

    def go_offline(self):
        #print 'go_offline', self.address, self.online
        if self.online:
            self.online = False
            Timeout(self.version_check, 60)

    def update_active(self, active_sessions, sessions_created, active_streams, preceived, ptransmitted):
        self.sessions_created = sessions_created
        self.active_sessions = active_sessions
        self.active_streams = active_streams
        self.preceived = preceived
        self.ptransmitted = ptransmitted
