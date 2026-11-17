from __future__ import annotations
import argparse
import bisect
import datetime
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import traceback
import psutil
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,
    QLabel,QPushButton,QDoubleSpinBox,QSpinBox,QComboBox,QColorDialog,QTabWidget,QLineEdit,
    QPlainTextEdit,QCheckBox,QSplitter,QScrollArea,QGroupBox,QStackedWidget,QSystemTrayIcon,QMenu,QStyle)
from . import __version__
from .ai import propose
from .history import History,SQLReplicator,replay,sessions,history_summary
from .kernel import Kernel
from .render import Viewport,surface_format
from .runtime import Runtime
from .projection import SignalView
from .telemetry import Telemetry

def spin(value,low=-1e9,high=1e9,decimals=5):
    widget=QDoubleSpinBox(); widget.setRange(low,high); widget.setDecimals(decimals); widget.setValue(value)
    widget.setSingleStep(.1); widget.setKeyboardTracking(False)
    return widget

class Window(QMainWindow):
    def __init__(self,args):
        super().__init__(); self.args=args
        self.setWindowTitle('ATOMVERSE POINT ENGINE · '+__version__)
        self.resize(1360,860)
        self.kernel=Kernel(args.sim_hz)
        self.history=History(args.data_dir/'history.db',self.kernel.state.point_id,
                             {'sim_hz':args.sim_hz,'record_hz':args.record_hz,'render_hz':args.render_hz,'version':__version__})
        self.sql=SQLReplicator(self.history.path,os.environ.get('ATOMVERSE_SQL_CONNECTION') or __import__('atomverse_point.history',fromlist=['SQL_CONNECTION']).SQL_CONNECTION) if not args.no_sql else None
        self.telemetry=Telemetry()
        self.runtime=Runtime(self.kernel,self.history,args.record_hz,self.telemetry)
        self.results=queue.Queue(); self.ai_pending=False; self.proposal=None; self.background_tasks=set()
        self.replay_states=[]; self.replay_times=[]; self.replay_start=0.; self.replay_active=False
        self.process=psutil.Process(); self.process.cpu_percent(None); self.last_metrics=0.; self.closing=False
        self.exit_errors=[]; self.verify_report=None; self.force_shutdown=False
        central=QWidget(); outer=QVBoxLayout(central); outer.setContentsMargins(18,14,18,14); outer.setSpacing(12)
        header=QHBoxLayout(); title=QLabel('⚛  ATOMVERSE  /  POINT ENGINE'); title.setObjectName('title')
        header.addWidget(title); header.addStretch(); header.addWidget(QLabel('MISSION 002  ·  COMPUTATION BEFORE PERCEPTION'))
        outer.addLayout(header)
        split=QSplitter(); outer.addWidget(split,1)
        scene=QWidget(); scene_layout=QVBoxLayout(scene); scene_layout.setContentsMargins(0,0,0,0)
        self.coordinates=QLabel(); self.coordinates.setObjectName('coordinates'); scene_layout.addWidget(self.coordinates)
        projection_row=QHBoxLayout(); projection_row.addWidget(QLabel('Perceptual representation'))
        self.projection_choice=QComboBox(); self.projection_choice.addItems(['sphere','wave','spiral','signal','data']); projection_row.addWidget(self.projection_choice); projection_row.addStretch(); scene_layout.addLayout(projection_row)
        self.views=QStackedWidget(); self.viewport=Viewport(); self.signal_view=SignalView(); self.data_view=QPlainTextEdit(); self.data_view.setReadOnly(True)
        self.views.addWidget(self.viewport); self.views.addWidget(self.signal_view); self.views.addWidget(self.data_view); scene_layout.addWidget(self.views,1)
        self.projection_choice.currentTextChanged.connect(self.switch_projection)
        camera=QHBoxLayout()
        for label,attr in [('Grid','grid'),('Axes','axes'),('Wall','wall'),('Movement trail','show_trail')]:
            cb=QCheckBox(label); cb.setChecked(True); cb.toggled.connect(lambda checked,a=attr:setattr(self.viewport,a,checked)); camera.addWidget(cb)
        self.focus_button=QPushButton('Focus point'); self.focus_button.clicked.connect(self.focus); camera.addWidget(self.focus_button)
        camera.addStretch(); scene_layout.addLayout(camera)
        self.performance=QLabel('Starting measurement…'); self.performance.setWordWrap(True); scene_layout.addWidget(self.performance)
        split.addWidget(scene)
        self.tabs=QTabWidget(); self.tabs.setMinimumWidth(360); split.addWidget(self.tabs); split.setSizes([950,380])
        self._controls(); self._paths(); self._frequency_tab(); self._history_tab(); self._ai_tab()
        self.keep_running=QCheckBox('Keep mathematical engine running when visualization closes'); self.keep_running.setChecked(args.keep_running)
        outer.addWidget(self.keep_running)
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.SP_ComputerIcon),self)
        self.tray.setToolTip('ATOMVERSE entity engine · running independently of visualization')
        tray_menu=QMenu(self); tray_menu.addAction('Show visualization',self.showNormal); tray_menu.addAction('Stop engine and quit',self.shutdown)
        self.tray.setContextMenu(tray_menu); self.tray.activated.connect(lambda reason:self.showNormal() if reason==QSystemTrayIcon.Trigger else None)
        QApplication.instance().setQuitOnLastWindowClosed(False)
        self.notice=QLabel('Commands act on one mathematical point. The sphere is its visible representation.'); self.notice.setWordWrap(True)
        outer.addWidget(self.notice); self.setCentralWidget(central)
        self.setStyleSheet('''
            QMainWindow,QWidget { background:#101a27; color:#d8e4f0; font-family:Segoe UI; font-size:12px; }
            QLabel#title { font-size:21px; font-weight:600; color:#8ce8e4; }
            QLabel#coordinates { background:#152638; padding:14px; font-family:Consolas; font-size:17px; }
            QGroupBox { border:1px solid #314255; border-radius:6px; margin-top:14px; padding:12px 8px 8px; }
            QGroupBox::title { subcontrol-origin:margin; left:10px; color:#8ce8e4; }
            QPushButton { background:#244356; border:1px solid #426277; border-radius:4px; padding:8px; }
            QPushButton:hover { background:#345e73; } QPushButton:disabled { color:#607080; }
            QLineEdit,QPlainTextEdit,QDoubleSpinBox,QSpinBox,QComboBox { background:#0b1520; border:1px solid #35495b; padding:5px; }
            QTabBar::tab { background:#192a3b; padding:10px; } QTabBar::tab:selected { background:#285165; }
            QScrollArea { border:0; }
        ''')
        QTimer.singleShot(100,self.runtime.start)
        self.timer=QTimer(self); self.timer.setTimerType(Qt.PreciseTimer); self.timer.timeout.connect(self.refresh); self.timer.start(max(1,round(1000/args.render_hz)))
        self.refresh_sessions()
        if args.verify_ui:
            self.verifier=GUIVerification(self,args.verify_ui)

    def tab(self,name):
        content=QWidget(); layout=QVBoxLayout(content); layout.setContentsMargins(10,10,10,10)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(content); self.tabs.addTab(scroll,name)
        return layout

    def row(self,layout,*widgets):
        row=QHBoxLayout()
        for w in widgets: row.addWidget(w)
        layout.addLayout(row)

    def button(self,label,callback):
        b=QPushButton(label); b.clicked.connect(callback); return b

    def _controls(self):
        layout=self.tab('Point')
        group=QGroupBox('Position · absolute or relative'); form=QFormLayout(group)
        self.xyz=[spin(0) for _ in range(3)]
        for key,w in zip('XYZ',self.xyz): form.addRow(key,w)
        self.at=spin(0,0,1e9,3); form.addRow('At simulation seconds (0 = now)',self.at)
        layout.addWidget(group)
        self.move_button=self.button('Teleport to XYZ',lambda:self.position(False))
        self.relative_button=self.button('Move by XYZ',lambda:self.position(True))
        self.row(layout,self.move_button,self.relative_button)
        group=QGroupBox('Appearance'); form=QFormLayout(group)
        self.radius=spin(.5,.001,1e6); self.radius.valueChanged.connect(lambda v:self.send({'action':'appearance','radius':v}))
        form.addRow('Radius',self.radius)
        self.color_button=self.button('Choose RGBA color',self.choose_color); form.addRow(self.color_button)
        self.intensity=spin(1,0,5,2); self.intensity.valueChanged.connect(lambda v:self.send({'action':'appearance','intensity':v})); form.addRow('Visual intensity',self.intensity)
        self.representation=QComboBox(); self.representation.addItems(['solid','wireframe','transparent','luminous','center'])
        self.representation.currentTextChanged.connect(lambda v:self.send({'action':'appearance','representation':v})); form.addRow('Representation',self.representation)
        layout.addWidget(group)
        group=QGroupBox('Wall interaction'); form=QFormLayout(group)
        self.collision=QComboBox(); self.collision.addItems(['pass','stop','reflect','slide','custom'])
        self.restitution=spin(1,0,1,2); self.wall_x=spin(5,-1e6,1e6)
        form.addRow('Mode',self.collision); form.addRow('Custom restitution',self.restitution); form.addRow('Plane X',self.wall_x)
        for signal in (self.collision.currentTextChanged,self.restitution.valueChanged,self.wall_x.valueChanged): signal.connect(self.apply_collision)
        layout.addWidget(group)
        self.pause_button=self.button('Pause',lambda:self.send({'action':'pause'}))
        self.resume_button=self.button('Resume',lambda:self.send({'action':'resume'}))
        self.stop_button=self.button('Stop',lambda:self.send({'action':'stop'}))
        self.reset_button=self.button('Reset position',lambda:self.send({'action':'reset'}))
        self.row(layout,self.pause_button,self.resume_button); self.row(layout,self.stop_button,self.reset_button)
        layout.addStretch()

    def _paths(self):
        layout=self.tab('Flow'); form=QFormLayout()
        self.path_kind=QComboBox(); self.path_kind.addItems(['line','circle','spiral','helix','custom','polyline'])
        form.addRow('Trajectory',self.path_kind)
        self.duration=spin(10,.001,86400,3); form.addRow('Duration (simulation seconds)',self.duration)
        self.amplitude=spin(2,0,1e6); form.addRow('Amplitude / radius',self.amplitude)
        self.frequency=spin(.2,-100,100); form.addRow('Frequency (cycles / sim second)',self.frequency)
        self.phase=spin(0,-1e6,1e6); form.addRow('Phase (radians)',self.phase)
        self.pitch=spin(.4,-1e6,1e6); form.addRow('Helix axial units / second',self.pitch)
        self.growth=spin(.1,-1e6,1e6); form.addRow('Spiral radius growth / second',self.growth)
        self.next_behavior=QComboBox(); self.next_behavior.addItems(['stop','continue']); form.addRow('After trajectory',self.next_behavior)
        layout.addLayout(form)
        layout.addWidget(QLabel('Line destination uses XYZ on the Point tab.\nCustom expressions are displacement from start.'))
        self.expressions=[QLineEdit(t) for t in ('2*cos(t)','2*sin(t)','0.4*t')]
        for name,w in zip('XYZ',self.expressions): self.row(layout,QLabel(name+'(t)'),w)
        self.polyline=QPlainTextEdit('[[1,0,0],[2,1,0],[3,1,2]]'); self.polyline.setMaximumHeight(80)
        layout.addWidget(QLabel('Polyline: absolute coordinate sequence (JSON)')); layout.addWidget(self.polyline)
        self.start_button=self.button('Start trajectory',self.start_path); layout.addWidget(self.start_button)
        group=QGroupBox('Continuous velocity'); form=QFormLayout(group)
        self.velocity=[spin(v) for v in (1,0,0)]; self.acceleration=[spin(0) for _ in range(3)]
        for name,v,a in zip('XYZ',self.velocity,self.acceleration):
            row=QWidget(); h=QHBoxLayout(row); h.setContentsMargins(0,0,0,0); h.addWidget(v); h.addWidget(a); form.addRow(name+' · velocity / acceleration',row)
        self.velocity_button=self.button('Apply velocity + acceleration',lambda:self.send({'action':'velocity','velocity':[w.value() for w in self.velocity],'acceleration':[w.value() for w in self.acceleration]}))
        form.addRow(self.velocity_button); layout.addWidget(group); layout.addStretch()

    def _history_tab(self):
        layout=self.tab('Memory')
        self.recording_status=QLabel(); self.recording_status.setWordWrap(True); layout.addWidget(self.recording_status)
        self.session_picker=QComboBox(); layout.addWidget(self.session_picker)
        self.row(layout,self.button('Refresh sessions',self.refresh_sessions),self.button('Replay selected',self.start_replay))
        self.live_button=self.button('Return to live point',self.return_live); layout.addWidget(self.live_button)
        self.restore_button=self.button('Restore displayed recorded state',self.restore_displayed); layout.addWidget(self.restore_button)
        self.row(layout,self.button('Create entity',lambda:self.send({'action':'create'})),self.button('Delete active entity',lambda:self.send({'action':'delete'})))
        self.replay_label=QLabel('LIVE · local journal records automatically'); self.replay_label.setWordWrap(True); layout.addWidget(self.replay_label)
        self.projection_status=QLabel(); self.projection_status.setWordWrap(True); layout.addWidget(self.projection_status)
        self.cancel_id=QLineEdit(); self.cancel_id.setPlaceholderText('Projection command UUID')
        layout.addWidget(self.cancel_id); layout.addWidget(self.button('Cancel active / scheduled command',lambda:self.send({'action':'cancel','command_id':self.cancel_id.text()})))
        note=QLabel('Recording and simulation run independently of rendering. Replay displays exact recorded samples. Capture gaps are counted and journaled.\n\nSimulation / render / capture rates can be set at launch with --sim-hz, --render-hz and --record-hz.\n\nTrail: historical positions of this one point. Connected independent points remain a future experiment.')
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch()

    def _frequency_tab(self):
        layout=self.tab('Frequency'); form=QFormLayout()
        self.osc_enabled=QCheckBox('Evolve oscillator'); self.osc_frequency=spin(1,0,1000); self.osc_amplitude=spin(1,0,1e6); self.osc_phase=spin(0,-1e6,1e6)
        form.addRow(self.osc_enabled); form.addRow('Frequency · cycles / sim second',self.osc_frequency); form.addRow('Amplitude · dimensionless',self.osc_amplitude); form.addRow('Phase · radians',self.osc_phase)
        layout.addLayout(form); self.osc_apply=self.button('Apply oscillator',self.apply_oscillator); layout.addWidget(self.osc_apply)
        self.osc_status=QLabel(); self.osc_status.setWordWrap(True); layout.addWidget(self.osc_status)
        self.hardware_enabled=QCheckBox('Observe hardware telemetry (opt in)'); self.hardware_enabled.toggled.connect(lambda v:setattr(self.telemetry,'enabled',v)); layout.addWidget(self.hardware_enabled)
        mapping_group=QGroupBox('Hardware → simulated amplitude'); mapping_form=QFormLayout(mapping_group)
        self.mapping_enabled=QCheckBox('Enable bounded modulation'); mapping_form.addRow(self.mapping_enabled)
        self.mapping_metric=QComboBox(); self.mapping_metric.addItems(['cpu_utilization','gpu_utilization','gpu_power_watts','cpu_clock_mhz','gpu_clock_mhz','memory_utilization']); mapping_form.addRow('Observed metric',self.mapping_metric)
        self.mapping_input_min=spin(0); self.mapping_input_max=spin(100); self.mapping_amp_min=spin(0,0,1e6); self.mapping_amp_max=spin(2,0,1e6)
        for name,widget in [('Input minimum',self.mapping_input_min),('Input maximum',self.mapping_input_max),('Output amplitude minimum',self.mapping_amp_min),('Output amplitude maximum',self.mapping_amp_max)]: mapping_form.addRow(name,widget)
        mapping_form.addRow(self.button('Apply mapping',self.apply_mapping)); self.disable_mapping=self.button('Disable modulation immediately',self.disable_modulation); mapping_form.addRow(self.disable_mapping); layout.addWidget(mapping_group)
        self.telemetry_label=QLabel('Hardware observation disabled'); self.telemetry_label.setWordWrap(True); layout.addWidget(self.telemetry_label)
        self.info_text=QPlainTextEdit('{}'); self.info_text.setMaximumHeight(70); layout.addWidget(QLabel('Information state · bounded JSON')); layout.addWidget(self.info_text); layout.addWidget(self.button('Apply information state',self.apply_information))
        label=QLabel('A·sin(2πft + phase) is a mathematical signal. Its amplitude is not physical energy. Hardware modulation is an inspectable numerical mapping.'); label.setWordWrap(True); layout.addWidget(label); layout.addStretch()

    def apply_oscillator(self): self.send({'action':'oscillator','frequency':self.osc_frequency.value(),'amplitude':self.osc_amplitude.value(),'phase':self.osc_phase.value(),'enabled':self.osc_enabled.isChecked()})
    def apply_mapping(self):
        enabled=self.mapping_enabled.isChecked()
        if enabled: self.hardware_enabled.setChecked(True)
        self.send({'action':'mapping','enabled':enabled,'metric':self.mapping_metric.currentText(),'input_min':self.mapping_input_min.value(),'input_max':self.mapping_input_max.value(),'amplitude_min':self.mapping_amp_min.value(),'amplitude_max':self.mapping_amp_max.value()})
    def disable_modulation(self):
        self.mapping_enabled.setChecked(False)
        try: self.runtime.submit({'action':'mapping','enabled':False})
        except Exception as exc: self.notice.setText(str(exc))
    def apply_information(self):
        try: self.send({'action':'information','information_state':json.loads(self.info_text.toPlainText())})
        except ValueError as exc: self.notice.setText('Rejected: '+str(exc))
    def switch_projection(self,name):
        if name=='sphere': self.views.setCurrentIndex(0)
        elif name=='data': self.views.setCurrentIndex(2)
        else: self.signal_view.mode=name; self.views.setCurrentIndex(1)
    def restore_displayed(self):
        if not self.replay_active: self.notice.setText('Select a recorded session and start replay before restoring.'); return
        state=dict(self.viewport.state); state.pop('event_seq',None)
        self.return_live(); self.send({'action':'restore','state':state})
    def shutdown(self): self.force_shutdown=True; self.close()

    def _ai_tab(self):
        layout=self.tab('AI')
        info=QLabel('Optional local Qwen interpretation. Review the structured proposal before applying it. Direct controls always work without AI.'); info.setWordWrap(True); layout.addWidget(info)
        self.ai_endpoint=QLineEdit(self.args.ai_endpoint); self.ai_model=QLineEdit(self.args.ai_model)
        self.ai_gpu=QSpinBox(); self.ai_gpu.setRange(0,16); self.ai_gpu.setValue(self.args.ai_gpu)
        form=QFormLayout(); form.addRow('Local Ollama endpoint',self.ai_endpoint); form.addRow('Model',self.ai_model); form.addRow('Requested GPU layers',self.ai_gpu); layout.addLayout(form)
        self.ai_text=QPlainTextEdit('Move the sphere to X 10, Y 5, Z 3.'); self.ai_text.setMaximumHeight(100); layout.addWidget(self.ai_text)
        self.ai_button=self.button('Ask Qwen for a proposal',self.ask_ai); layout.addWidget(self.ai_button)
        self.ai_result=QPlainTextEdit(); self.ai_result.setReadOnly(True); layout.addWidget(self.ai_result)
        self.apply_ai=self.button('Apply validated proposal',self.apply_proposal); self.apply_ai.setEnabled(False); layout.addWidget(self.apply_ai)

    def send(self,c):
        try:
            if self.replay_active: self.return_live()
            if self.at.value()>0 and 'at' not in c and c['action'] not in ('pause','resume','stop','reset'): c=dict(c,at=self.at.value())
            self.runtime.submit(c); self.notice.setText('Queued: '+c['action']+' · accepted execution and durable recording appear in Memory.')
        except Exception as exc: self.notice.setText('Rejected: '+str(exc))

    def position(self,relative): self.send({'action':'translate' if relative else 'teleport','delta' if relative else 'position':[w.value() for w in self.xyz]})
    def choose_color(self):
        c=QColorDialog.getColor(QColor.fromRgbF(*self.runtime.read()['color']),self,'Point RGBA',QColorDialog.ShowAlphaChannel)
        if c.isValid(): self.send({'action':'appearance','color':[c.redF(),c.greenF(),c.blueF(),c.alphaF()]})
    def apply_collision(self,*_):
        self.send({'action':'collision','mode':self.collision.currentText(),'restitution':self.restitution.value(),'wall_x':self.wall_x.value()})
    def start_path(self):
        kind=self.path_kind.currentText(); spec={'kind':kind,'duration':self.duration.value(),'next':self.next_behavior.currentText()}
        if kind=='line': spec['target']=[w.value() for w in self.xyz]
        elif kind in ('circle','spiral','helix'):
            for name in ('amplitude','frequency','phase','pitch','growth'): spec[name]=getattr(self,name).value()
        elif kind=='custom': spec['expressions']=[w.text() for w in self.expressions]
        else:
            try: spec['points']=json.loads(self.polyline.toPlainText())
            except ValueError: self.notice.setText('Rejected: invalid coordinate sequence JSON'); return
        self.send({'action':'trajectory','trajectory':spec})
    def focus(self): self.viewport.target=tuple(self.viewport.state['position']); self.viewport.distance=max(5,self.viewport.state['radius']*5)

    def background(self,name,fn):
        if name in self.background_tasks or self.closing: return
        self.background_tasks.add(name)
        def work():
            try: result=fn(); self.results.put((name,result,None))
            except Exception as exc: self.results.put((name,None,f'{type(exc).__name__}: {exc}'))
        threading.Thread(target=work,name='point-'+name,daemon=True).start()
    def refresh_sessions(self): self.background('sessions',lambda:sessions(self.history.path))
    def start_replay(self):
        sid=self.session_picker.currentData()
        if not sid: return
        self.runtime.submit({'action':'pause'})
        self.background('replay',lambda:replay(self.history.path,sid))
    def return_live(self):
        self.replay_active=False; self.replay_states=[]; self.replay_times=[]
        self.replay_label.setText('LIVE · resume explicitly when ready')
    def ask_ai(self):
        if self.ai_pending: return
        self.ai_pending=True; self.ai_button.setEnabled(False); self.apply_ai.setEnabled(False)
        self.ai_result.setPlainText('Waiting for local Qwen… simulation continues independently.')
        text=self.ai_text.toPlainText(); state=self.runtime.read(); endpoint=self.ai_endpoint.text(); model=self.ai_model.text(); gpu=self.ai_gpu.value()
        telemetry=self.telemetry.read() if self.telemetry.enabled else None
        def interpret():
            context={'history':history_summary(self.history.path,self.history.session_id,3)}
            if telemetry: context['hardware_telemetry']={k:telemetry[k] for k in ('classification','values','units','fresh')}
            return propose(text,state,endpoint,model,gpu,context=context)
        self.background('ai',interpret)
    def apply_proposal(self):
        if self.proposal:
            command=self.proposal['command']
            if command['action']=='history_query': self.background('history_query',lambda:history_summary(self.history.path,self.history.session_id,command['limit']))
            elif command['action']!='explain': self.send(command)
            self.apply_ai.setEnabled(False)

    def refresh(self):
        while True:
            try: name,result,error=self.results.get_nowait()
            except queue.Empty: break
            self.background_tasks.discard(name)
            if name=='ai':
                self.ai_pending=False; self.ai_button.setEnabled(True)
                self.ai_result.setPlainText(error or json.dumps(result,indent=2))
                self.proposal=result; self.apply_ai.setEnabled(not error and result['command']['action']!='explain')
                if result:
                    # Move persistence off the UI thread as well as model inference.
                    snap=self.runtime.read()
                    self.background('ai_record',lambda r=result,s=snap:self.history.record({'kind':'ai_interpretation','tick':s['tick'],'sim_time':s['sim_time'],'payload':r}))
            elif error: self.notice.setText(error)
            elif name=='history_query': self.ai_result.setPlainText(json.dumps(result,indent=2))
            elif name=='sessions':
                self.session_picker.clear()
                for sid,created,_ in result:
                    date=datetime.datetime.fromtimestamp(created/1e9).strftime('%m-%d %H:%M:%S')
                    self.session_picker.addItem(date+' · '+sid[:8],sid)
            elif name=='replay':
                self.replay_states=result; self.replay_times=[s['sim_time'] for s in result]
                self.replay_start=time.perf_counter(); self.replay_active=bool(result)
        state=self.runtime.read()
        if self.replay_active:
            elapsed=time.perf_counter()-self.replay_start+self.replay_times[0]
            index=max(0,bisect.bisect_right(self.replay_times,elapsed)-1)
            state=self.replay_states[index]
            self.replay_label.setText(f'RECORDED HISTORY · sample {index+1}/{len(self.replay_states)} · no interpolation')
        self.viewport.set_state(state,not self.replay_active); self.viewport.wall_x=self.kernel.wall_x
        if self.views.currentIndex()==0: self.viewport.update()
        elif self.views.currentIndex()==1: self.signal_view.set_state(state)
        elif time.perf_counter()-self.last_metrics>=.5: self.data_view.setPlainText(json.dumps(state,indent=2))
        p=state['position']; mode='REPLAY' if self.replay_active else state['simulation_status']
        self.coordinates.setText(f'X {p[0]: .6f}    Y {p[1]: .6f}    Z {p[2]: .6f}\n{mode}  ·  t {state["sim_time"]:.3f} s  ·  tick {state["tick"]:,}')
        now=time.perf_counter()
        if now-self.last_metrics>=.5:
            self.last_metrics=now; h=self.history.stats(); r=self.runtime.stats(); g=self.viewport.stats()
            self.osc_status.setText(f'SIMULATED s(t) = {state.get("oscillator_value",0):.7f}\nEffective amplitude {state.get("effective_amplitude",1):.5f} · {state.get("telemetry_status","DISABLED")}')
            hardware=self.telemetry.read()
            if self.telemetry.enabled and hardware: self.telemetry_label.setText('OBSERVED TELEMETRY\n'+json.dumps(hardware['values'],indent=2)+'\nFresh: '+str(hardware['fresh']))
            else: self.telemetry_label.setText('Hardware observation disabled / awaiting sample')
            sql=f'{self.sql.status} · replicated {self.sql.rows:,}' if self.sql else 'disabled'
            self.recording_status.setText(f'LOCAL JOURNAL · {h["written"]:,} events committed\nSamples {h["samples_written"]:,} · dropped {h["dropped_samples"]:,}\nQueue {h["queue_depth"]} · SQL: {sql}\nSession {self.history.session_id}')
            self.projection_status.setText('Last command: '+str(self.runtime.last_command_id))
            self.performance.setText(f'SIM {self.args.sim_hz} Hz · RENDER {g["average_fps"]:.1f} FPS (target {self.args.render_hz}) · CAPTURE {self.args.record_hz} Hz\nJournal {h["events_per_second"]:.0f} events/s · process CPU {self.process.cpu_percent(None):.1f}% · RSS {self.process.memory_info().rss/2**20:.0f} MiB · overruns {r["timing_overruns"]}\nGPU: {g["graphics"].get("renderer","initializing")}')
            if r['error'] or h['error']: self.notice.setText('RECORDING / SIMULATION FAULT: '+str(r['error'] or h['error']))

    def closeEvent(self,event):
        if self.keep_running.isChecked() and not self.force_shutdown:
            self.tray.show(); self.hide(); event.ignore(); return
        if self.closing: event.accept(); return
        self.closing=True; self.timer.stop()
        for component in (self.runtime,self.telemetry,self.sql,self.history):
            if component:
                try: component.close()
                except Exception as exc: self.exit_errors.append(str(exc))
        if self.verify_report is not None:
            self.verify_report['clean_shutdown']=not self.exit_errors and not self.runtime.thread.is_alive() and not self.history.thread.is_alive()
            self.verify_report['shutdown_errors']=self.exit_errors
            self.verify_report['final_recording']=self.history.stats()
            if self.exit_errors: self.verify_report['status']='FAIL'
            (self.args.verify_ui/'gui-verification.json').write_text(json.dumps(self.verify_report,indent=2),encoding='utf-8')
        event.accept()
        self.tray.hide(); QApplication.instance().quit()

class GUIVerification:
    """Clicks the actual native controls, inspects displayed state, saves rendered pixels."""
    def __init__(self,window,destination):
        self.w=window; self.dest=destination; destination.mkdir(parents=True,exist_ok=True)
        self.checks=[]; self.stage=0; self.saved=None; self.failure=None
        self.timer=QTimer(window); self.timer.timeout.connect(self.advance); self.timer.start(400)
    def check(self,name,condition):
        self.checks.append({'name':name,'passed':bool(condition),'method':'actual GUI control and runtime observation'})
        if not condition: raise AssertionError(name)
    def advance(self):
        from PySide6.QtTest import QTest
        w=self.w; s=w.runtime.read()
        try:
            if self.stage==0:
                self.check('one primary sphere at origin',s['position']==(0.,0.,0.) and bool(s['point_id']))
                self.check('hardware OpenGL context',bool(w.viewport.gpu_info.get('renderer')) and 'GDI Generic' not in str(w.viewport.gpu_info))
                for b,v in zip(w.xyz,(-2,1,3)): b.setValue(v)
                QTest.mouseClick(w.move_button,Qt.LeftButton)
            elif self.stage==1:
                self.check('absolute positive and negative coordinates',s['position']==(-2.,1.,3.))
                w.radius.setValue(.8); w.send({'action':'appearance','color':[.2,.8,.4,.7]})
                self.saved=s['position']; w.viewport.yaw+=45; w.viewport.distance=18
            elif self.stage==2:
                self.check('camera independent; radius and RGBA',s['position']==self.saved and s['radius']==.8 and tuple(s['color'])==(.2,.8,.4,.7))
                w.path_kind.setCurrentText('line'); w.duration.setValue(.6)
                for b,v in zip(w.xyz,(1,2,-1)): b.setValue(v)
                QTest.mouseClick(w.start_button,Qt.LeftButton)
            elif self.stage==4:
                self.check('line reaches destination',all(abs(a-b)<1e-8 for a,b in zip(s['position'],(1,2,-1))))
                w.path_kind.setCurrentText('helix'); w.duration.setValue(5)
                QTest.mouseClick(w.start_button,Qt.LeftButton)
            elif self.stage==6:
                self.check('helical motion changes position',s['position']!=(1.,2.,-1.))
                QTest.mouseClick(w.pause_button,Qt.LeftButton)
            elif self.stage==7: self.saved=w.runtime.read()
            elif self.stage==8:
                self.check('pause freezes simulation time and coordinates',s['tick']==self.saved['tick'] and s['position']==self.saved['position'])
                QTest.mouseClick(w.resume_button,Qt.LeftButton)
            elif self.stage==9:
                self.check('resume advances point',s['position']!=self.saved['position'])
                QTest.mouseClick(w.stop_button,Qt.LeftButton); w.collision.setCurrentText('stop')
                for b,v in zip(w.xyz,(4,0,0)): b.setValue(v)
                QTest.mouseClick(w.move_button,Qt.LeftButton)
                w.velocity[0].setValue(10); QTest.mouseClick(w.velocity_button,Qt.LeftButton)
            elif self.stage==11:
                self.check('stop at sphere-expanded wall boundary',abs(s['position'][0]-4.2)<1e-8 and s['simulation_status']=='STOPPED')
                w.collision.setCurrentText('pass'); QTest.mouseClick(w.velocity_button,Qt.LeftButton)
            elif self.stage==13:
                self.check('pass through wall',s['position'][0]>5.8)
                QTest.mouseClick(w.stop_button,Qt.LeftButton)
                w.history.flush(); w.refresh_sessions()
            elif self.stage==15: w.start_replay()
            elif self.stage==17:
                self.check('history replay loads recorded states',w.replay_active and len(w.replay_states)>20)
                self.check('replay does not mutate live position',w.runtime.read()['simulation_status']=='PAUSED')
                w.return_live(); w.send({'action':'reset'}); w.focus()
            elif self.stage==19:
                w.viewport.grabFramebuffer().save(str(self.dest/'viewport.png'))
                w.grab().save(str(self.dest/'application.png'))
                self.check('real framebuffer captured',(self.dest/'viewport.png').stat().st_size>10000)
            elif self.stage==20:
                w.osc_enabled.setChecked(True); w.osc_frequency.setValue(2); w.osc_amplitude.setValue(3); w.osc_phase.setValue(1.5708)
                QTest.mouseClick(w.osc_apply,Qt.LeftButton)
            elif self.stage==21:
                from .oscillator import signal
                self.check('oscillator controls calculate simulated signal',s['oscillator_enabled'] and abs(s['oscillator_value']-signal(3,2,1.5708,s['oscillator_time']))<1e-9)
                QTest.mouseClick(w.pause_button,Qt.LeftButton)
            elif self.stage==22:
                self.entity_checkpoint=s
                for mode in ('wave','spiral','signal','data'): w.projection_choice.setCurrentText(mode)
            elif self.stage==23:
                self.check('perceptual view changes preserve authoritative state',s==self.entity_checkpoint)
                w.projection_choice.setCurrentText('sphere'); w.send({'action':'delete'})
            elif self.stage==24:
                self.check('delete removes active entity but retains history',not s['entity_active'] and w.history.written>0)
                w.send({'action':'create'})
            elif self.stage==25:
                self.check('create generates one new entity identity',s['entity_active'] and s['point_id']!=self.entity_checkpoint['point_id'])
                w.send({'action':'restore','state':self.entity_checkpoint})
            elif self.stage==26:
                self.check('restore reconstructs historical identity and parameters',s['point_id']==self.entity_checkpoint['point_id'] and s['frequency']==2 and s['simulation_status']=='PAUSED')
                QTest.mouseClick(w.resume_button,Qt.LeftButton)
            elif self.stage==27:
                self.hidden_tick=s['tick']; w.keep_running.setChecked(True); w.close()
            elif self.stage==28:
                self.check('entity evolves while visualization is closed',not w.isVisible() and s['tick']>self.hidden_tick and w.runtime.thread.is_alive())
                w.keep_running.setChecked(False); w.showNormal()
            elif self.stage==29:
                self.telemetry_started=time.perf_counter(); w.mapping_enabled.setChecked(True); w.apply_mapping()
            elif self.stage==30:
                if not w.telemetry.read():
                    if time.perf_counter()-self.telemetry_started>5: raise AssertionError('Hardware observation unavailable')
                    return
            elif self.stage==31:
                self.check('real opt-in telemetry modulates bounded amplitude',s['telemetry_status']=='MAPPED' and 0<=s['effective_amplitude']<=2)
                QTest.mouseClick(w.disable_mapping,Qt.LeftButton); w.hardware_enabled.setChecked(False)
            elif self.stage==32:
                self.check('hardware modulation can be disabled',not s['telemetry_mapping']['enabled'] and s['effective_amplitude']==s['amplitude'])
                w.grab().save(str(self.dest/'mission002-application.png'))
                if not w.args.verify_ai: self.finish(); return
                self.ai_start_tick=s['tick']; self.ai_start_frames=w.viewport.frames; self.ai_wait_started=time.perf_counter()
                w.ask_ai()
            elif self.stage==33:
                if w.ai_pending:
                    if time.perf_counter()-self.ai_wait_started>110: raise AssertionError('AI GUI deadline exceeded')
                    return
                self.check('real Qwen structured proposal in packaged GUI',bool(w.proposal) and w.proposal['command']=={'action':'teleport','position':(10.,5.,3.)})
                self.check('simulation and rendering continue during inference',s['tick']>self.ai_start_tick+100 and w.viewport.frames>self.ai_start_frames+20)
                QTest.mouseClick(w.apply_ai,Qt.LeftButton)
            elif self.stage==35:
                self.check('reviewed AI command executes through kernel',s['position']==(10.,5.,3.))
                self.finish(); return
            self.stage+=1
        except Exception as exc:
            self.failure=f'{type(exc).__name__}: {exc}'; self.finish()
    def finish(self):
        self.timer.stop(); w=self.w
        w.verify_report={'status':'FAIL' if self.failure else 'PASS','error':self.failure,'checks':self.checks,
                         'packaged':bool(getattr(sys,'frozen',False)),'version':__version__,'renderer':w.viewport.stats(),
                         'runtime':w.runtime.stats(),'recording':w.history.stats(),'rss_bytes':w.process.memory_info().rss,
                         'sql_status':w.sql.status if w.sql else 'disabled','sql_rows':w.sql.rows if w.sql else 0}
        if w.args.verify_ai: w.verify_report['ai_proposal']=w.proposal
        QTimer.singleShot(100,w.shutdown)

def main(argv=None):
    p=argparse.ArgumentParser(description='One spherical computational point. Native controls require no AI.')
    default=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ATOMVERSE-POINT-ENGINE'
    p.add_argument('--data-dir',type=Path,default=default)
    p.add_argument('--sim-hz',type=int,default=240); p.add_argument('--record-hz',type=int,default=120); p.add_argument('--render-hz',type=int,default=60)
    p.add_argument('--no-sql',action='store_true'); p.add_argument('--verify-ui',type=Path)
    p.add_argument('--verify-ai',action='store_true',help='With --verify-ui, also test the configured real local model')
    p.add_argument('--keep-running',action='store_true'); p.add_argument('--headless',action='store_true')
    p.add_argument('--seconds',type=float,default=10); p.add_argument('--command-file',type=Path); p.add_argument('--snapshot-out',type=Path)
    p.add_argument('--ai-endpoint',default='http://127.0.0.1:11434'); p.add_argument('--ai-model',default='qwen3.8:27b'); p.add_argument('--ai-gpu',type=int,default=8)
    args=p.parse_args(argv)
    if not 1<=args.record_hz<=args.sim_hz<=2000 or not 1<=args.render_hz<=144: p.error('Require 1 <= record Hz <= simulation Hz <= 2000 and 1 <= rendering Hz <= 144')
    args.data_dir.mkdir(parents=True,exist_ok=True)
    if args.headless:
        if not 0<args.seconds<=86400: p.error('Headless duration must be 0 < seconds <= 86400')
        from .headless import run
        return run(args)
    surface_format(); app=QApplication(sys.argv[:1]); app.setApplicationName('ATOMVERSE POINT ENGINE')
    window=Window(args); window.show(); code=app.exec()
    if window.exit_errors or (window.verify_report and window.verify_report['status']!='PASS'): return 1
    return code

if __name__=='__main__': raise SystemExit(main())
