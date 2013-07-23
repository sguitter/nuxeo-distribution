# (C) Copyright 2009 Nuxeo SAS <http://nuxeo.com>
# Author: bdelbosc@nuxeo.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
"""
Simulate a Nuxeo Drive client
"""
import time
import uuid
from funkload.utils import Data
from utils import extractToken


def extractIds(text):
    """Extract ids in a getChildren json response."""
    ret = text.split('"id":"')
    ret = [id[:id.find('"')] for id in ret[1:]]
    return ret


def extractDownloadUrl(text):
    """Extract dowload url from json response"""
    return extractToken(text, 'downloadURL":"', '"')


class DriveClient:
    """Class to simulate Nuxeo Drive client."""

    def __init__(self, fl, device_id=None, token=None):
        self.fl = fl
        if device_id is None:
            self.device_id = uuid.uuid1().hex
        else:
            self.device_id = device_id
        if token:
            self.token = token
        else:
            self.token = None
        # populated when starting drive
        self.root_ids = []
        self.sync_ids = ''

    def bind_server(self, user, password):
        fl = self.fl
        server_url = fl.server_url
        fl.addHeader('X-Devince-Id', self.device_id)
        fl.addHeader('X-User-Id', user)
        fl.addHeader('X-Application-Name', 'Nuxeo Drive')
        fl.setBasicAuth(user, password)
        fl.get(server_url + "/site/automation/",
               description="Hello automation with basic auth")
        fl.assert_('NuxeoDrive.GetTopLevelFolder' in fl.getBody(),
                   "No NuxeoDrive automation operations found")
        fl.get(server_url + "/authentication/token",
               params=[['applicationName', 'Nuxeo Drive'],
                       ['deviceDescription',
                        'Funkload Test ' + time.asctime()],
                       ['revoke', 'false'],
                       ['deviceId', self.device_id],
                       ['permission', 'ReadWrite']],
               description="Bind server")
        fl.clearBasicAuth()
        if self.token is None:
            self.token = fl.getBody()
        fl.addHeader('X-Authentication-Token', self.token)

        fl.get(server_url + "/site/automation/",
               description="Hello automation with token")
        fl.assert_('NuxeoDrive.GetTopLevelFolder' in fl.getBody(),
                   "Fail to access automation with the token: " + self.token)
        fl.post(server_url + "/site/automation/NuxeoDrive.GetTopLevelFolder",
                Data('application/json+nxrequest', '''{"params": {}}'''),
                description="Get top level folder")
        fl.assert_('canCreateChild' in fl.getBody())

    def navigate(self, ids):
        if len(ids) == 0:
            return
        fl = self.fl
        server_url = fl.server_url
        for id in ids:
            fl.post(server_url +
                    "/site/automation/NuxeoDrive.GetFileSystemItem",
                    Data('application/json+nxrequest',
                         '{"params": {"id": "' + id + '"}}'),
                    description="GetFileSystemItem " + id)
            download_url = extractDownloadUrl(fl.getBody())
            if download_url is not None:
                fl.get(server_url + '/' + download_url,
                       description="Download file")
            if '"folder":true' not in fl.getBody():
                continue
            fl.post(server_url + "/site/automation/NuxeoDrive.GetChildren",
                    Data('application/json+nxrequest',
                         '{"params": {"id": "' + id + '"}}'),
                    description="GetChildren " + id)
            children = extractIds(fl.getBody())
            self.navigate(children)

    def start_drive(self):
        fl = self.fl
        server_url = fl.server_url
        fl.get(server_url + "/site/automation/",
               description="Hello automation with token")

        fl.addHeader('X-Nxdocumentproperties', '*')
        fl.addHeader('Accept', 'application/json+nxentity, */*')
        fl.post(server_url + "/site/automation/NuxeoDrive.GetChangeSummary",
                Data('application/json+nxrequest', '''{"params": {}}'''),
                description="GetChangeSummary")
        fl.assert_('activeSynchronizationRootDefinitions' in fl.getBody())
        self.sync_ids = extractToken(
            fl.getBody(), 'activeSynchronizationRootDefinitions":"', '"')
        fl.post(server_url + "/site/automation/NuxeoDrive.GetFileSystemItem",
                Data('application/json+nxrequest',
                     '''{"params": {"id": "org.nuxeo.drive.service.impl.DefaultTopLevelFolderItemFactory#"}}'''),
                description="GetFileSystemItem")
        fl.assert_('canCreateChild' in fl.getBody())

        fl.post(server_url + "/site/automation/NuxeoDrive.GetChildren",
                Data('application/json+nxrequest',
                     '''{"params": {"id": "org.nuxeo.drive.service.impl.DefaultTopLevelFolderItemFactory#"}}'''),
                description="GetChildren")

        ids = extractIds(fl.getBody())
        self.root_ids = ids
        fl.assert_(len(ids) > 0, "No root to sync on server")
        self.navigate(ids)

    def get_update(self):
        self.fl.post(self.fl.server_url +
                     "/site/automation/NuxeoDrive.GetChangeSummary",
                     Data('application/json+nxrequest',
                          '{"params": {"lastSyncDate": ' +
                          str(int(time.time() * 1000)) +
                          ', "lastSyncActiveRootDefinitions": "' +
                          self.sync_ids + '"}}'),
                     description="GetChangeSummary")