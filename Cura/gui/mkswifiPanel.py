__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import wx
import socket
import sys
import logging
import threading
from multiprocessing import queues
from Cura.util import profile
import mimetools
import urllib2
import os
import time
from sceneView import httpUploadDataStreamMKS
import httplib

reload(sys)
sys.setdefaultencoding('utf-8')
#Panel to mkswifi control printer.
class mkswifiPanel(wx.Panel):
    def __init__(self, parent, callback=None):
        wx.Panel.__init__(self, parent, -1)
        print('mkswifi loaded')
        sys.setrecursionlimit(1000000)
        self.callback = callback

        self.sceneview = self.GetParent().GetParent().GetParent().GetParent().GetParent().scene

        self.port = 8080
        self._socket = None
        self._address = None
        self._isConnect = False
        self._isPrinting = False
        self._isPause = False
        self._isSending = False
        self._ischanging = False
        self._printing_filename = ""
        self._printing_progress = 0
        self._printing_time = 0
        self._sdFileList = False
        self.sdFiles = []
        self._ishotBedpreHeat = False
        self._isextruder1preHeat = False
        self._isextruder2preHeat = False
        self._ishotBedR = False
        self._isextruder1R = False
        self._isextruder2R = False

        self.extruderCount = int(profile.getMachineSetting('extruder_amount'))
        self.bagSizer = wx.GridBagSizer(0, 0)
        # ConnectToPrinter
        self.connectTitle = wx.StaticText(self, -1, _("Connect printer"))
        self.connectTitle.SetFont(wx.Font(wx.SystemSettings.GetFont(wx.SYS_ANSI_VAR_FONT).GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.FONTWEIGHT_BOLD))
        self.ipLabel = wx.lib.stattext.GenStaticText(self, -1, _("IP Address"))
        # self.label.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
        # self.label.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseExit)
        ip = profile.getMachineSetting('ip_address')
        self.ipCtrl = wx.TextCtrl(self, -1, ip)
        self.ipCtrl.Bind(wx.EVT_TEXT, self.OnIpAddressChange)
        # self.ctrl.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
        # self.ctrl.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseExit)
        self.connectBtn = wx.Button(self, -1, _("Connect"))
        self.connectBtn.Bind(wx.EVT_BUTTON, lambda e: self.controlPrinter())
        # self.connectBtn.Bind(wx.EVT_BUTTON, lambda e: self.sendFile())
        # self.unConnectBtn = wx.Button(self, -1, _("UNConnect"))
        # self.unConnectBtn.Bind(wx.EVT_BUTTON, lambda e: self.controlPrinter())
        self.sendJobBtn = wx.Button(self, -1, _("Send Job"))
        self.sendJobBtn.Bind(wx.EVT_BUTTON, lambda e: self.sendFile())
        self.bagSizer.Add(self.connectTitle, (0, 0), flag=wx.EXPAND | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(wx.StaticLine(self), (1, 0), (1, 4), flag=wx.EXPAND | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(self.ipLabel, (2, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(self.ipCtrl, (2, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.EXPAND, border=10)
        self.bagSizer.Add(self.connectBtn, (2, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.LEFT , border=10)
        # self.bagSizer.Add(self.unConnectBtn, (3, 1), flag=wx.ALL, border=5)
        self.bagSizer.Add(self.sendJobBtn, (3, 0), (1, 3), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP |wx.EXPAND, border=10)

        # ControlPrinter
        self.controlTitle = wx.StaticText(self, -1, _("Control printer"))
        self.controlTitle.SetFont(wx.Font(wx.SystemSettings.GetFont(wx.SYS_ANSI_VAR_FONT).GetPointSize(), wx.FONTFAMILY_DEFAULT, wx.NORMAL, wx.FONTWEIGHT_BOLD))
        self.hotBedLabel = wx.lib.stattext.GenStaticText(self, -1, _("Hot Bed"))
        self.hotBedCurrentLabel = wx.lib.stattext.GenStaticText(self, -1, _("Current temp (deg C)"))
        self.hotBedCurrenttext = wx.StaticText(self, -1, _("0"))
        self.hotBedTargetLabel = wx.lib.stattext.GenStaticText(self, -1, _("Target temp (deg C)"))
        self.hotBedTargetCtrl = wx.TextCtrl(self, -1, "0")
        self.hotBedTargetCtrl.Bind(wx.EVT_SET_FOCUS, self.setFocusBed)
        self.hotBedTargetCtrl.Bind(wx.EVT_KILL_FOCUS, self.killFocusBed)
        self.hotBedpreHeatBtn = wx.Button(self, -1, _("PreHeat"))
        self.hotBedpreHeatBtn.Bind(wx.EVT_BUTTON, lambda e: self.hotBedpreHeat())
        self.bagSizer.Add(self.controlTitle, (4, 0), flag=wx.EXPAND | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(wx.StaticLine(self), (5, 0), (1, 4), flag=wx.EXPAND | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(self.hotBedLabel, (6, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(self.hotBedCurrentLabel, (7, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.hotBedCurrenttext, (7, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.hotBedTargetLabel, (8, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.hotBedTargetCtrl, (8, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.hotBedpreHeatBtn, (8, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP, border=10)

        # self.hotBedTargetCtrl.SetEditable(False)

        self.extrLabel1 = wx.lib.stattext.GenStaticText(self, -1, _("Extruder 1"))
        self.extrCurrentLabel1 = wx.lib.stattext.GenStaticText(self, -1, _("Current temp (deg C)"))
        self.extrCurrenttext1 = wx.StaticText(self, -1, _("0"))
        self.extrTargetLabel1 = wx.lib.stattext.GenStaticText(self, -1, _("Target temp (deg C)"))
        self.extrTargetCtrl1 = wx.TextCtrl(self, -1, "0")
        self.extrTargetCtrl1.Bind(wx.EVT_SET_FOCUS, self.setFocusE1)
        self.extrTargetCtrl1.Bind(wx.EVT_KILL_FOCUS, self.killFocusE1)
        self.preHeatBtn1 = wx.Button(self, -1, _("PreHeat"))
        self.preHeatBtn1.Bind(wx.EVT_BUTTON, lambda e: self.extruder1PreHeat())
        self.bagSizer.Add(self.extrLabel1, (9, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.LEFT, border=10)
        self.bagSizer.Add(self.extrCurrentLabel1, (10, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.extrCurrenttext1, (10, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.extrTargetLabel1, (11, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.extrTargetCtrl1, (11, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.preHeatBtn1, (11, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP, border=10)
        tag = 0
        if self.extruderCount > 1:
            tag = 3
            self.extrLabel2 = wx.lib.stattext.GenStaticText(self, -1, _("Extruder 2"))
            self.extrCurrentLabel2 = wx.lib.stattext.GenStaticText(self, -1, _("Current temp (deg C)"))
            self.extrCurrenttext2 = wx.StaticText(self, -1, _("0"))
            self.extrTargetLabel2 = wx.lib.stattext.GenStaticText(self, -1, _("Target temp (deg C)"))
            self.extrTargetCtrl2 = wx.TextCtrl(self, -1, "0")
            self.extrTargetCtrl2.Bind(wx.EVT_SET_FOCUS, self.setFocusE2)
            self.extrTargetCtrl2.Bind(wx.EVT_KILL_FOCUS, self.killFocusE2)
            self.preHeatBtn2 = wx.Button(self, -1, _("PreHeat"))
            self.preHeatBtn2.Bind(wx.EVT_BUTTON, lambda e: self.extruder2PreHeat())
            self.bagSizer.Add(self.extrLabel2, (12, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.LEFT, border=10)
            self.bagSizer.Add(self.extrCurrentLabel2, (13, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                              border=10)
            self.bagSizer.Add(self.extrCurrenttext2, (13, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                              border=10)
            self.bagSizer.Add(self.extrTargetLabel2, (14, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                              border=10)
            self.bagSizer.Add(self.extrTargetCtrl2, (14, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                              border=10)
            self.bagSizer.Add(self.preHeatBtn2, (14, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP, border=10)

        self.printingNameLabel = wx.lib.stattext.GenStaticText(self, -1, _("Printing Job"))
        self.printingName = wx.StaticText(self, -1, "------")
        self.printingTimeLabel = wx.lib.stattext.GenStaticText(self, -1, _("Printing Time"))
        self.printingTime = wx.StaticText(self, -1, "00:00:00")
        self.totalTimeLabel = wx.lib.stattext.GenStaticText(self, -1, _("Print progress"))
        self.totalTime = wx.StaticText(self, -1, "0%")
        self.bagSizer.Add(self.printingNameLabel, (12 + tag, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.printingName, (12 + tag, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.printingTimeLabel, (13 + tag, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.printingTime, (13 + tag, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.totalTimeLabel, (14 + tag, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.totalTime, (14 + tag, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)

        self.coolDownBtn = wx.Button(self, -1, _("Cool Down"))
        self.coolDownBtn.Bind(wx.EVT_BUTTON, lambda e: self.coolDown())
        self.pauseBtn = wx.Button(self, -1, _("Pause"))  # Resume
        self.pauseBtn.Bind(wx.EVT_BUTTON, lambda e: self.pauseOrResume())
        self.stopBtn = wx.Button(self, -1, _("Stop"))
        self.stopBtn.Bind(wx.EVT_BUTTON, lambda e: self.stopPrint())
        self.bagSizer.Add(self.coolDownBtn, (15 + tag, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.pauseBtn, (15 + tag, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)
        self.bagSizer.Add(self.stopBtn, (15 + tag, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT,
                          border=10)

        self.delSDFileBtn = wx.Button(self, -1, _("Delete SD File"))
        self.delSDFileBtn.Bind(wx.EVT_BUTTON, lambda e: self.delSDFile())
        self.printSDFileBtn = wx.Button(self, -1, _("Print SD File"))
        self.printSDFileBtn.Bind(wx.EVT_BUTTON, lambda e: self.printSDFile())
        self.sendFileBtn = wx.Button(self, -1, _("Send File"))
        self.sendFileBtn.Bind(wx.EVT_BUTTON, lambda e: self.showSelectFile())
        self.bagSizer.Add(self.delSDFileBtn, (16 + tag, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.printSDFileBtn, (16 + tag, 1), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)
        self.bagSizer.Add(self.sendFileBtn, (16 + tag, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, border=10)

        self.SetSizer(self.bagSizer)
        self._update_timer = None
        self._recv_timer = None
        self._command_queue = queues.Queue()

        self.updateConnectUI()
        self.uploadProcessDlg = None

    def controlPrinter(self):
        if self._isConnect:
            self.disConnect()
        else:
            self.connectPrinter()

    def connectPrinter(self):
        self._address = self.ipCtrl.GetValue()
        logging.debug("connectPrinter" + self._address)
        if self._address is None or self._address is '':
            return
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.connectBtn.SetLabel(_("Connecting"))
            self._socket.connect((self._address, 8080))
        except Exception as e:
            self.sceneview.notification.message("Connect failed, please check your IP address.")
            self.connectBtn.SetLabel(_("Connect"))
            return
        if self._socket is None:
            logging.debug("_socket fail")
            return
        self.sceneview.notification.message("Connect success.")
        self._isConnect = True
        self.updateConnectUI()
        self.startTimer()
        self._sendCommand("M20")

    def startTimer(self):
        if self._update_timer is not None:
            self._update_timer.cancel()
            self._update_timer = None
        if self._recv_timer is not None:
            self._recv_timer.cancel()
            self._recv_timer = None
        self._update_timer = threading.Timer(2, self._update)
        self._recv_timer = threading.Timer(2, self.onRead)
        self._update_timer.start()
        self._recv_timer.start()

    def _update(self):
        if self._socket is not None:
            if self._command_queue.qsize() > 0:
                _send_data = ""
            else:
                _send_data = "M105\r\nM997\r\n"
            if self.isBusy():
                _send_data += "M994\r\nM992\r\nM27\r\n"
            while self._command_queue.qsize() > 0:
                _queue_data = self._command_queue.get()
                if "M23" in _queue_data:
                    self._socket.send(_queue_data.encode(sys.getfilesystemencoding()))
                    continue
                if "M24" in _queue_data:
                    self._socket.send(_queue_data.encode(sys.getfilesystemencoding()))
                    continue
                if self.isBusy():
                    if "M20" in _queue_data:
                        continue
                _send_data += _queue_data
            self._socket.send(_send_data.encode(sys.getfilesystemencoding()))
            self._update_timer.run()
        else:
            self.disConnect()
            self.connectPrinter()

    def coolDown(self):
        self._sendCommand("M104 S0\r\n M140 S0\r\n M106 S255")

    def pauseOrResume(self):
        if self._isPause:
            self._ischanging = True
            self._sendCommand("M24")
        else:
            self._sendCommand("M25")
    def stopPrint(self):
        dlg = wx.MessageDialog(self, _("Do you want to stop print?"), _("Tips"), wx.YES_NO)
        if dlg.ShowModal() == wx.ID_YES:
            self._sendCommand("M26")
        dlg.Destroy()

    def hotBedpreHeat(self):
        self._ishotBedR = False
        if self._ishotBedpreHeat:
            self._sendCommand(["M140 S0"])
            self._ishotBedpreHeat = False
        else:
            temp = int(self.hotBedTargetCtrl.GetValue())
            if temp:
                self._sendCommand(["M140 S%s" % temp])
                self._ishotBedpreHeat = True
        self.updatehotBedpreHeatUI()

    def extruder1PreHeat(self):
        self._isextruder1R = False
        if self._isextruder1preHeat:
            self._sendCommand(["M104 S0 T0"])
            self._isextruder1preHeat = False
        else:
            temp = self.extrTargetCtrl1.GetValue()
            if temp:
                self._sendCommand(["M104 S%s T0" % temp])
                self._isextruder1preHeat = True
        self.updateE1preHeatUI()

    def extruder2PreHeat(self):
        self._isextruder2R = False
        if self._isextruder2preHeat:
            self._sendCommand(["M104 S0 T1"])
            self._isextruder2preHeat = False
        else:
            temp = self.extrTargetCtrl2.GetValue()
            if temp:
                self._sendCommand(["M104 S%s T1" % temp])
                self._isextruder2preHeat = True
        self.updateE2preHeatUI()

    def setFocusBed(self, e):
        self._ishotBedR = True
        e.Skip()

    def killFocusBed(self, e):
        self._ishotBedR = False
        e.Skip()

    def setFocusE1(self, e):
        self._isextruder1R = True
        e.Skip()

    def killFocusE1(self, e):
        self._isextruder1R = False
        e.Skip()

    def setFocusE2(self, e):
        self._isextruder2R = True
        e.Skip()

    def killFocusE2(self, e):
        self._isextruder2R = False
        e.Skip()

    def _sendCommand(self, cmd):
        if self._ischanging:
            if "G28" in cmd or "G0" in cmd:
                return
        if self.isBusy():
            if "M20" in cmd:
                return
        # if self._socket and self._socket.state() == 2 or self._socket.state() == 3:
        if self._socket is not None:
            if isinstance(cmd, str):
                self._command_queue.put(cmd + "\r\n")
            elif isinstance(cmd, list):
                for eachCommand in cmd:
                    self._command_queue.put(eachCommand + "\r\n")

    def disConnect(self):
        logging.debug("disConnect")
        self._update_timer.cancel()
        self._recv_timer.cancel()
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._isConnect = False
        self.updateConnectUI()

    def onRead(self):
        # logging.debug("onRead")
        if not self._socket:
            logging.debug("onRead not self._socket")
            return
        try:
            if not self._isConnect:
                self._isConnect = True
            data = self._socket.recv(1024)
            # logging.debug("recv data:" + repr(data))
            # data = data.replace("\r", "").replace("\n", "")
            # logging.debug("recv replace:" + data)
            lines = data.split("ok")
            for s in lines:
                # print("s----------" + s)
                if "T" in s and "B" in s and "T0" in s:
                    t0_temp = s[s.find("T0:") + len("T0:"):s.find("T1:")]
                    t1_temp = s[s.find("T1:") + len("T1:"):s.find("@:")]
                    bed_temp = s[s.find("B:") + len("B:"):s.find("T0:")]
                    t0_nowtemp = t0_temp[0:t0_temp.find("/")]
                    t0_targettemp = t0_temp[t0_temp.find("/") + 1:len(t0_temp)]
                    t1_nowtemp = t1_temp[0:t1_temp.find("/")]
                    t1_targettemp = t1_temp[t1_temp.find("/") + 1:len(t1_temp)]
                    bed_nowtemp = bed_temp[0:bed_temp.find("/")]
                    bed_targettemp = bed_temp[bed_temp.find("/") + 1:len(bed_temp)]
                    self.extrCurrenttext1.SetLabel(t0_nowtemp)
                    if not self._isextruder1R:
                        self.extrTargetCtrl1.SetValue(t0_targettemp)
                    if t0_nowtemp == t0_targettemp:
                        self._isextruder1preHeat = False
                        self.updateE1preHeatUI()
                    if self.extruderCount > 1:
                        self.extrCurrenttext2.SetLabel(t1_nowtemp)
                        if not self._isextruder2R:
                            self.extrTargetCtrl2.SetValue(t1_targettemp)
                        if t1_nowtemp == t1_targettemp:
                            self._isextruder2preHeat = False
                            self.updateE2preHeatUI()
                    self.hotBedCurrenttext.SetLabel(bed_nowtemp)
                    if not self._ishotBedR:
                        self.hotBedTargetCtrl.SetValue(bed_targettemp)
                    if bed_nowtemp == bed_targettemp:
                        self._ishotBedpreHeat = False
                        self.updatehotBedpreHeatUI()
                    continue
                if "M997" in s:
                    job_state = "offline"
                    if "IDLE" in s:
                        self._isPrinting = False
                        self._isPause = False
                        job_state = 'idle'
                    elif "PRINTING" in s:
                        self._isPrinting = True
                        self._isPause = False
                        job_state = 'printing'
                    elif "PAUSE" in s:
                        self._isPrinting = False
                        self._isPause = True
                        job_state = 'paused'
                    if self._isPrinting:
                        self._ischanging = False
                    self.updatePrintUI()
                    continue
                if "M994" in s:
                    if self.isBusy() and s.rfind("/") != -1:
                        self._printing_filename = s[s.rfind("/") + 1:s.rfind(";")]
                    else:
                        self._printing_filename = ""
                    self.printingName.SetLabel(self._printing_filename)
                    continue
                if "M992" in s:
                    if self.isBusy():
                        tm = s[s.find("M992") + len("M992"):len(s)].replace(" ", "")
                        mms = tm.split(":")
                        self._printing_time = int(mms[0]) * 3600 + int(mms[1]) * 60 + int(mms[2])
                    else:
                        self._printing_time = 0
                        tm = "00:00:00"
                    self.printingTime.SetLabel(tm)
                    continue
                if "M27" in s:
                    if self.isBusy():
                        self._printing_progress = float(s[s.find("M27") + len("M27"):len(s)].replace(" ", ""))
                        # totaltime = self._printing_time / self._printing_progress * 100
                    else:
                        self._printing_progress = 0
                        # totaltime = self._printing_time * 100
                    self.totalTime.SetLabel(str(self._printing_progress) + "%")
                    continue
                if 'Begin file list' in s:
                    self._sdFileList = True
                    self.sdFiles = []
                if self._sdFileList:
                    files = data.split("\n")
                    for file in files:
                        if file.lower().endswith("gcode") or file.lower().endswith("gco") or file.lower().endswith("g"):
                            self.sdFiles.append(file)
                if 'End file list' in s:
                    self._sdFileList = False
                    continue
                if s.startswith("Upload"):
                    logging.debug("upload error" + s)
                    continue
            self._recv_timer.run()
        except Exception as e:
            if e.message.find("errno"):
                self.disConnect()
                self.connectPrinter()
            logging.debug("onRead Exception-------" + str(e.message))

    def isBusy(self):
        return self._isPrinting or self._isPause

    def OnIpAddressChange(self, e):
        setting = profile.settingsDictionary["ip_address"]
        setting.setValue(self.ipCtrl.GetValue())

    def updateConnectUI(self):
        if self._isConnect:
            self.ipCtrl.Enable(False)
            self.connectBtn.SetLabel(_("UNConnect"))
            self.sendJobBtn.Enable(True)
            self.hotBedTargetCtrl.Enable(True)
            self.hotBedpreHeatBtn.Enable(True)
            self.extrTargetCtrl1.Enable(True)
            self.preHeatBtn1.Enable(True)
            if self.extruderCount > 1:
                self.extrTargetCtrl2.Enable(True)
                self.preHeatBtn2.Enable(True)
            self.printingName.Enable(False)
            self.printingTime.Enable(False)
            self.totalTime.Enable(False)
            self.coolDownBtn.Enable(True)
            self.pauseBtn.Enable(False)
            self.stopBtn.Enable(False)
            self.printSDFileBtn.Enable(True)
            self.delSDFileBtn.Enable(True)
            self.sendFileBtn.Enable(True)
        else:
            self.ipCtrl.Enable(True)
            self.connectBtn.SetLabel(_("Connect"))
            self.sendJobBtn.Enable(False)
            self.hotBedTargetCtrl.Enable(False)
            self.hotBedpreHeatBtn.Enable(False)
            self.extrTargetCtrl1.Enable(False)
            self.preHeatBtn1.Enable(False)
            if self.extruderCount > 1:
                self.extrTargetCtrl2.Enable(False)
                self.preHeatBtn2.Enable(False)
            self.printingName.Enable(False)
            self.printingTime.Enable(False)
            self.totalTime.Enable(False)
            self.coolDownBtn.Enable(False)
            self.pauseBtn.Enable(False)
            self.stopBtn.Enable(False)
            self.printSDFileBtn.Enable(False)
            self.delSDFileBtn.Enable(False)
            self.sendFileBtn.Enable(False)

    def updatePrintUI(self):
        if self._isPrinting:
            self.printingName.Enable(True)
            self.printingTime.Enable(True)
            self.totalTime.Enable(True)
            self.pauseBtn.Enable(True)
            self.pauseBtn.SetLabel(_("Pause"))
            self.stopBtn.Enable(True)
            self.coolDownBtn.Enable(False)
            self.hotBedTargetCtrl.Enable(False)
            self.hotBedpreHeatBtn.Enable(False)
            self.extrTargetCtrl1.Enable(False)
            self.preHeatBtn1.Enable(False)
            if self.extruderCount > 1:
                self.extrTargetCtrl2.Enable(False)
                self.preHeatBtn2.Enable(False)
            self.printSDFileBtn.Enable(False)
            self.delSDFileBtn.Enable(False)
            self.sendFileBtn.Enable(False)
        elif self._isPause:
            self.printingName.Enable(True)
            self.printingTime.Enable(True)
            self.totalTime.Enable(True)
            self.pauseBtn.Enable(True)
            self.pauseBtn.SetLabel(_("Resume"))
            self.stopBtn.Enable(True)
            self.coolDownBtn.Enable(True)
            self.hotBedTargetCtrl.Enable(True)
            self.hotBedpreHeatBtn.Enable(True)
            self.extrTargetCtrl1.Enable(True)
            self.preHeatBtn1.Enable(True)
            if self.extruderCount > 1:
                self.extrTargetCtrl2.Enable(True)
                self.preHeatBtn2.Enable(True)
            self.printSDFileBtn.Enable(False)
            self.delSDFileBtn.Enable(False)
            self.sendFileBtn.Enable(False)
        else:
            self.printingName.Enable(False)
            self.printingTime.Enable(False)
            self.totalTime.Enable(False)
            self.pauseBtn.Enable(False)
            self.stopBtn.Enable(False)
            self.coolDownBtn.Enable(True)
            self.hotBedTargetCtrl.Enable(True)
            self.hotBedpreHeatBtn.Enable(True)
            self.extrTargetCtrl1.Enable(True)
            self.preHeatBtn1.Enable(True)
            if self.extruderCount > 1:
                self.extrTargetCtrl2.Enable(True)
                self.preHeatBtn2.Enable(True)
            self.printSDFileBtn.Enable(True)
            self.delSDFileBtn.Enable(True)
            self.sendFileBtn.Enable(True)

    def updatehotBedpreHeatUI(self):
        if self._ishotBedpreHeat:
            self.hotBedTargetCtrl.Enable(False)
            self.hotBedpreHeatBtn.SetLabel(_("Cancel"))
        else:
            self.hotBedTargetCtrl.Enable(True)
            self.hotBedpreHeatBtn.SetLabel(_("PreHeat"))

    def updateE1preHeatUI(self):
        if self._isextruder1preHeat:
            self.extrTargetCtrl1.Enable(False)
            self.preHeatBtn1.SetLabel(_("Cancel"))
        else:
            self.extrTargetCtrl1.Enable(True)
            self.preHeatBtn1.SetLabel(_("PreHeat"))

    def updateE2preHeatUI(self):
        if self._isextruder2preHeat:
            self.extrTargetCtrl2.Enable(False)
            self.preHeatBtn2.SetLabel(_("Cancel"))
        else:
            self.extrTargetCtrl2.Enable(True)
            self.preHeatBtn2.SetLabel(_("PreHeat"))

    def sendFile(self):
        print('sendFile')
        if self._update_timer is not None:
            self._update_timer.cancel()
        if self._recv_timer is not None:
            self._recv_timer.cancel()
        # res = self.callbackmskwifi()
        res = self.sceneview.mkswifiStartPrint()
        self.startTimer()
        if res["status"]:
            self._sendCommand(["M23 %s" % res["filename"]])
            self._sendCommand("M24")

    def delSDFile(self):
        self._sendCommand("M20")
        dlg = wx.SingleChoiceDialog(self, _("Please select file to delete"), _("Delete SD File"), self.sdFiles)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetStringSelection()
            if len(filename) < 1:
                return
            askdlg = wx.MessageDialog(self, _("Do you want to delete %s?") % filename, _("Tips"), wx.YES_NO)
            if askdlg.ShowModal() == wx.ID_YES:
                self._sendCommand(["M30 1:/" + filename])
                self._sendCommand("M20")
                askdlg.Destroy()
        dlg.Destroy()

    def printSDFile(self):
        self._sendCommand("M20")
        # setting = profile.settingsDictionary["printer_file_list"]
        # filelist = setting.getType()
        dlg = wx.SingleChoiceDialog(self, _("Please select file to print"),_( "Print SD File"), self.sdFiles)
        # dlg = wx.SingleChoiceDialog(self, "Please select file to print", "Print SD File", filelist)
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetStringSelection()
            if len(filename) < 1:
                return
            askdlg = wx.MessageDialog(self, _("Do you want to print %s?") % filename, _("Tips"), wx.YES_NO)
            if askdlg.ShowModal() == wx.ID_YES:
                self._sendCommand(["M23 " + filename])
                self._sendCommand("M24")
                askdlg.Destroy()
        dlg.Destroy()

    def showSelectFile(self):
        dlg = wx.FileDialog(self, _("Please select file to send"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        wildcardList = ';'.join(map(lambda s: '*' + s, ['.g', '.gcode', '.GCODE']))
        wildcardFilter = "GCode files (%s)|%s;%s" % (wildcardList, wildcardList, wildcardList.upper())
        dlg.SetWildcard(wildcardFilter)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        filename = dlg.GetPaths()
        dlg.Destroy()
        if len(filename) < 1:
            return False
        self.sendGcodeFile(filename[0])

    def progressCallback(self, readpos, totallen):
        pro = float(readpos)/float(totallen) * 100
        if self.uploadProcessDlg is not None:
            self.uploadProcessDlg.Update(pro)

    def sendGcodeFile(self, path):
        self._update_timer.cancel()
        self._recv_timer.cancel()
        filename = path[path.rfind("\\") + 1:]
        filename = self.sceneview.validateFilename(filename)
        if not filename:
            self.sceneview.notification.message("Canceled send file")
            return
        single_string_file_data = ""
        with open(path, "r") as f:
            single_string_file_data += f.read()
        ipAddr = profile.getMachineSetting('ip_address')
        retrymax = 3
        count = 0

        for i in xrange(retrymax):
            try:
                if self.uploadProcessDlg is not None:
                    self.uploadProcessDlg.Destroy()
                    self.uploadProcessDlg = None
                self.uploadProcessDlg = wx.ProgressDialog(_("File is uploading, please wait."), _("Uploading"))
                s = httpUploadDataStreamMKS(self.progressCallback)
                boundary = mimetools.choose_boundary()
                s.write('--%s\r\n' % (boundary))
                s.write('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename)
                s.write('Content-Type: application/octet-stream\r\n')
                s.write('Content-Transfer-Encoding: binary\r\n')
                s.write('\r\n')
                s.write(single_string_file_data)
                s.write('\r\n')
                s.write('--%s--\r\n' % (boundary))
                http_url = 'http://%s/upload?X-Filename=%s' % (ipAddr, filename)
                # buld http request
                req = urllib2.Request(http_url, data=s)
                # header
                req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 6.2; WOW64; rv:22.0) Gecko/20100101 Firefox/22.0')
                req.add_header('Connection', 'keep-alive')
                req.add_header('Content-Length', len(s))
                req.add_header('Content-Type', 'application/json')
                # post data to server
                resp = urllib2.urlopen(req, timeout=500)
                # get response
                qrcont = resp.read()
                print("qrcont===" + qrcont)
                if self.uploadProcessDlg is not None:
                    self.uploadProcessDlg.Destroy()
                    self.uploadProcessDlg = None
                self.startTimer()
                if qrcont == "{\"err\":0}":
                    self.sceneview.notification.message("Upload success")
                    mydlg = wx.MessageDialog(self, _("Successful, do you want to print %s?") % filename, _("Upload success"), wx.YES_NO)
                    if mydlg.ShowModal() == wx.ID_YES:
                        self._sendCommand(["M23 " + filename])
                        self._sendCommand("M24")
                        mydlg.Destroy()
                    mydlg.Destroy()
                else:
                    self.sceneview.notification.message("Upload failed")
                    mydlg = wx.MessageDialog(self, _("Failed, do you want to retry?"), _("Upload failed"), wx.YES_NO)
                    if mydlg.ShowModal() == wx.ID_YES:
                        self.sendGcodeFile(path)
                        mydlg.Destroy()
                    mydlg.Destroy()
                break
            except Exception as e:
                # self._http.close()
                print("Exception as e--------" + str(e))
                if i < retrymax - 1:
                    if self.uploadProcessDlg is not None:
                        self.uploadProcessDlg.Destroy()
                        self.uploadProcessDlg = None
                    time.sleep(1)
                    continue
                else:
                    if self.uploadProcessDlg is not None:
                        self.uploadProcessDlg.Destroy()
                        self.uploadProcessDlg = None
                    self.sceneview.notification.message("Upload failed, please try again later.")
                    break

    def getNameInList(self, name):
        for i in xrange(len(self.sdFiles)):
            if self.sdFiles[i] == name:
                return True
        return False

    def updateProfileToControls(self):
        logging.debug("updateProfileToControls")
