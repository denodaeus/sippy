# Copyright (c) 2003-2005 Maxim Sobolev. All rights reserved.
# Copyright (c) 2006-2007 Sippy Software, Inc. All rights reserved.
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

from UaStateGeneric import UaStateGeneric
from CCEvents import CCEventRing, CCEventConnect, CCEventFail, CCEventRedirect, \
  CCEventDisconnect, CCEventPreConnect
from SipContact import SipContact
from SipAddress import SipAddress
from Timeout import TimeoutAbs

class UasStateTrying(UaStateGeneric):
    sname = 'Trying(UAS)'

    def recvEvent(self, event):
        if isinstance(event, CCEventRing):
            scode = event.getData()
            if scode == None:
                code, reason, body = (180, 'Ringing', None)
            else:
                code, reason, body = scode
                if code == 100:
                    return None
                if body != None and self.ua.on_local_sdp_change != None and body.needs_update:
                    self.ua.on_local_sdp_change(body, lambda x: self.ua.recvEvent(event))
                    return None
            self.ua.lSDP = body
            self.ua.sendUasResponse(code, reason, body)
            if self.ua.no_progress_timer != None:
                self.ua.no_progress_timer.cancel()
                self.ua.no_progress_timer = None
                if self.ua.expire_time != None:
                    self.ua.expire_timer = TimeoutAbs(self.ua.expires, self.ua.expire_time)
            if self.ua.p1xx_ts == None:
                self.ua.p1xx_ts = event.rtime
            return (UasStateRinging, self.ua.ring_cbs, event.rtime, event.origin, code)
        elif isinstance(event, CCEventConnect) or isinstance(event, CCEventPreConnect):
            code, reason, body = event.getData()
            if body != None and self.ua.on_local_sdp_change != None and body.needs_update:
                self.ua.on_local_sdp_change(body, lambda x: self.ua.recvEvent(event))
                return None
            if event.extra_headers != None:
                extra_headers = tuple(event.extra_headers)
            else:
                extra_headers = None
            self.ua.lSDP = body
            if self.ua.no_progress_timer != None:
                self.ua.no_progress_timer.cancel()
                self.ua.no_progress_timer = None
            if isinstance(event, CCEventConnect):
                self.ua.sendUasResponse(code, reason, body, self.ua.lContact, ack_wait = False, \
                  extra_headers = extra_headers)
                if self.ua.expire_timer != None:
                    self.ua.expire_timer.cancel()
                    self.ua.expire_timer = None
                self.ua.startCreditTimer(event.rtime)
                self.ua.connect_ts = event.rtime
                return (UaStateConnected, self.ua.conn_cbs, event.rtime, event.origin)
            else:
                self.ua.sendUasResponse(code, reason, body, self.ua.lContact, ack_wait = True, \
                  extra_headers = extra_headers)
                return (UaStateConnected,)
        elif isinstance(event, CCEventRedirect):
            scode = event.getData()
            if scode == None:
                scode = (500, 'Failed', None, None)
            self.ua.sendUasResponse(scode[0], scode[1], scode[2], SipContact(address = SipAddress(url = scode[3])))
            if self.ua.expire_timer != None:
                self.ua.expire_timer.cancel()
                self.ua.expire_timer = None
            if self.ua.no_progress_timer != None:
                self.ua.no_progress_timer.cancel()
                self.ua.no_progress_timer = None
            self.ua.disconnect_ts = event.rtime
            return (UaStateFailed, self.ua.fail_cbs, event.rtime, event.origin, scode[0])
        elif isinstance(event, CCEventFail):
            scode = event.getData()
            if scode == None:
                scode = (500, 'Failed')
            extra_headers = []
            if event.extra_headers != None:
                extra_headers.extend(event.extra_headers)
            if event.challenge != None:
                extra_headers.append(event.challenge)
            if len(extra_headers) == 0:
                extra_headers = None
            else:
                extra_headers = tuple(extra_headers)
            self.ua.sendUasResponse(scode[0], scode[1], reason_rfc3326 = event.reason, \
              extra_headers = extra_headers)
            if self.ua.expire_timer != None:
                self.ua.expire_timer.cancel()
                self.ua.expire_timer = None
            if self.ua.no_progress_timer != None:
                self.ua.no_progress_timer.cancel()
                self.ua.no_progress_timer = None
            self.ua.disconnect_ts = event.rtime
            return (UaStateFailed, self.ua.fail_cbs, event.rtime, event.origin, scode[0])
        elif isinstance(event, CCEventDisconnect):
            #import sys, traceback
            #traceback.print_stack(file = sys.stdout)
            self.ua.sendUasResponse(500, 'Disconnected', reason_rfc3326 = event.reason)
            if self.ua.expire_timer != None:
                self.ua.expire_timer.cancel()
                self.ua.expire_timer = None
            if self.ua.no_progress_timer != None:
                self.ua.no_progress_timer.cancel()
                self.ua.no_progress_timer = None
            self.ua.disconnect_ts = event.rtime
            return (UaStateDisconnected, self.ua.disc_cbs, event.rtime, event.origin, self.ua.last_scode)
        #print 'wrong event %s in the Trying state' % event
        return None

    def cancel(self, rtime, req):
        self.ua.disconnect_ts = rtime
        self.ua.changeState((UaStateDisconnected, self.ua.disc_cbs, rtime, self.ua.origin))
        event = CCEventDisconnect(rtime = rtime, origin = self.ua.origin)
        if req != None:
            try:
                event.reason = req.getHFBody('reason')
            except:
                pass
        self.ua.emitEvent(event)

if not globals().has_key('UasStateRinging'):
    from UasStateRinging import UasStateRinging
if not globals().has_key('UaStateFailed'):
    from UaStateFailed import UaStateFailed
if not globals().has_key('UaStateConnected'):
    from UaStateConnected import UaStateConnected
if not globals().has_key('UaStateDisconnected'):
    from UaStateDisconnected import UaStateDisconnected
