import os
import json
import dearpygui.dearpygui as dpg
import cv2
import numpy as np
from tkinter import filedialog

from video_analyzer import VideoAnalyzer
from log_manager import LogManager

#TODO Probably ought to refactor this class to be a static, all things considered
#TODO Maybe implement an auto sort feature to the frame window settings to sort by chronological order
#TODO Consider a Filter system for applying similar actions (IE lock/unlock) to various UI elements on screen.  Possible flag implementation underneath for glue.
class Gui:

    def __init__(self):
        self._update_frame = False
        self._current_frame = 0
        self._analyzer = VideoAnalyzer()
        self._setting_ranges = []
        self._frame_count = None
        self._fps = None
        self._raw_report_results = []
        self._total_x_data = []
        self._total_y_data = []
        self._boxed_x_data = []
        self._boxed_y_data = []
        self._scored_x_data = []
        self._scored_y_data = []
        self._video = None
        self._slider = None
        self.has_saved = True
        self.report_filename = None
        self.exit = False
        try:
            self._context = dpg.create_context()
            dpg.create_viewport(title='Video Bites', width=835, height=750, resizable = False)

            dpg.add_texture_registry(show=False)          

            with dpg.window(id='ModalErrorPopup', label='Error', modal=True, pos=(320,300), width=400, height=150, no_resize=True, show=False):
                with dpg.group():
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=45)
                        dpg.add_text(default_value='An error has occurred that has caused\n\t the application to crash.\n\nPlease contact support and send a copy\n\tof the most recent error logs.')
                    dpg.add_spacer(height=15)
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=170)
                        dpg.add_button(id='ConfirmErrorButton', label='Ok', callback=Gui._cb_close_error_popup, user_data={'ctr':self})

            with dpg.window(id='ModalConfirmExit',label='Save Report?', modal=True, width=515, height=100, pos=(170,300), no_resize=True,show=False):
                dpg.add_text(default_value='You have not saved this report.  Do you wish to quit without saving?')
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=138)
                    dpg.add_button(label='Save', callback=Gui._cb_save_and_quit, user_data={'ctr':self})
                    dpg.add_button(label='Dont\'t Save', callback=Gui._cb_exit, user_data={'ctr':self})
                    dpg.add_button(label='Cancel', callback=Gui._cb_cancel_exit, user_data={'ctr':self})

            with dpg.window(id='ModalNewSetting', modal=True, width=515, height=200, no_resize=True,show=False):
                with dpg.group():
                    dpg.add_text(default_value='Specify number of seconds for running average time window.')
                    with dpg.group(horizontal=True):
                        dpg.add_text(default_value='Starting Frame:')
                        dpg.add_input_int(id='NewSettingStartInput', width=100, min_value=0, default_value=1)
                        dpg.add_spacer(width=6)
                        dpg.add_text(id='StartErrorText', default_value='', color=(255,0,0,255))
                    with dpg.group(horizontal=True):
                        dpg.add_text(default_value='Ending Frame:')
                        dpg.add_spacer(width=6)
                        dpg.add_input_int(id='NewSettingEndInput', width=100, min_value=0, max_value=59, default_value=1)
                        dpg.add_spacer(width=6)
                        dpg.add_text(id='EndErrorText', default_value='', color=(255,0,0,255))
                    dpg.add_spacer(height=10)
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=100)
                        dpg.add_text(id='NewSettingGeneralErrorText', default_value='', color=(255,0,0,255))
                    dpg.add_spacer(height=10)
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=325)
                        dpg.add_button(id='NewSettingConfirmBtn', width=70, label='Confirm', callback=Gui._cb_confirm_new_setting_modal, user_data={'ctr':self})
                        dpg.add_button(width=70, label='Cancel', callback=Gui._cb_close_new_setting_modal, user_data={'ctr':self})

            with dpg.window(id='MainWindow', width=950, height=750, no_title_bar=True, no_resize=True, no_move=True, pos=(0,19), no_close=True):
                with dpg.menu_bar(label='MainMenuBar'):
                    with dpg.menu(label='File'):
                        dpg.add_menu_item(label='Open', callback=Gui._cb_open, user_data={'ctr':self})
                        dpg.add_menu_item(label='Save', callback=Gui._cb_save, user_data={'ctr':self, 'file-override':False})
                        dpg.add_menu_item(label='Save As...', callback=Gui._cb_save, user_data={'ctr':self, 'file-override':True})
                        dpg.add_menu_item(label='Exit', callback=Gui._cb_attempt_exit, user_data={'ctr':self, 'file-override':True})
                with dpg.group():
                    with dpg.group(horizontal=True):
                        with dpg.child_window(label='AnalysisSettings', width=(260), height=(350), border=False):
                            with dpg.group(horizontal=True):
                                dpg.add_spacer(width=5)
                                dpg.add_text(id='AnalysisSettingsLabel', default_value='Analysis Settings')
                                dpg.add_button(id='NewSettingBtn', callback=Gui._cb_add_setting, user_data={'ctr':self},label='+')
                            with dpg.child_window(id='SettingsContainer', width=(230), height=(320), pos=(5, 30), no_scrollbar=False):
                                pass

                        with dpg.child_window(id='PreviewSection', width=(622), height=(350), no_scrollbar=False, border=False):
                            with dpg.group(horizontal=True):
                                dpg.add_button(id='SrcBtn', label='Source...', callback=Gui._cb_choose_src_vid, user_data={'ctr':self})
                                dpg.add_text(id='TgtFilepath', default_value='mp4 file not yet chosen')
                            with dpg.child_window(id='VideoPreview', width=535, height=303, border=False):
                                with dpg.drawlist(width=528, height=297, tag="DrawArea"):
                                    dpg.draw_rectangle(tag='test-rect',pmin=[0,0],pmax=[528,297], fill=[21,21,21], color=[21,21,21])

                            self._slider = dpg.add_slider_int(id='VideoPosSlider', min_value=0, max_value=0, width=529,enabled=True, callback=Gui._cb_frame_slider, user_data={'ctr':self})
                            
                    dpg.add_spacer(height=10)
                    
                    with dpg.child_window(id='ResultGraphs', width=800, height=270, no_scrollbar=False):
                        with dpg.tab_bar(id='GraphTabBar', reorderable=False, user_data={'ctr':self}):
                            
                            with dpg.tab(id='TotalCommentTab', label='Total Comments'):
                                with dpg.plot(tag='TotalPlot', label='Total Comments Over Time', width=785, height=208):
                                    dpg.add_plot_legend()
                                    dpg.add_plot_axis(dpg.mvXAxis, label='Frame Number', tag='XAxisTotal', lock_min=True)
                                    dpg.add_plot_axis(dpg.mvYAxis, label='Total Number of Comments', tag='YAxisTotal', lock_min=True)
                                    dpg.add_line_series(self._total_x_data, self._total_y_data, label='Total Comments', parent='YAxisTotal', tag='TotalSeries')

                            with dpg.tab(id='BoxedCommentTab', label='Grouped Comments'):
                                with dpg.group():
                                    with dpg.plot(tag='BoxedPlot', label='Comments per Window', width=785, height=208):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label='Frame Number', tag='XAxisBoxed', lock_min=True)
                                        dpg.add_plot_axis(dpg.mvYAxis, label='Total Number of Comments', tag='YAxisBoxed', lock_min=True)
                                        dpg.add_bar_series(self._boxed_x_data, self._boxed_y_data, label='Comments in 5.0 Second Window', parent='YAxisBoxed', tag='BoxedSeries')
                                    with dpg.group(horizontal=True):
                                        dpg.add_input_int(tag='WindowSizeInput',width = 130, default_value=300,min_value=1, min_clamped=True)
                                        dpg.add_text(default_value='Window Size (frames)')

                            with dpg.tab(id='ScoredCommentTab', label='Engagement Scores'):
                                with dpg.group():
                                    with dpg.plot(tag='ScoredPlot', label='Engagement Score Over Time', width=785, height=208):
                                        dpg.add_plot_legend()
                                        dpg.add_plot_axis(dpg.mvXAxis, label='Frame Number', tag='XAxisScored', lock_min=True)
                                        dpg.add_plot_axis(dpg.mvYAxis, label='Engagement Score', tag='YAxisScored', lock_min=True)
                                        dpg.add_line_series(self._scored_x_data, self._scored_y_data, label='Engagement Score Over Time', parent='YAxisScored', tag='ScoredSeries')
                                    with dpg.group():
                                        with dpg.group(horizontal=True):
                                            dpg.add_input_float(tag='PointValueInput', width = 130, default_value=2.0,step=1, min_value=0, min_clamped=True)
                                            dpg.add_text(default_value='Point Value')
                                            dpg.add_spacer(width=80)
                                            dpg.add_input_float(tag='DecayRateInput', width = 130, default_value=0.002,step=0.001, min_value=0, min_clamped=True)
                                            dpg.add_text(default_value='Decay Rate (per frame)')

                    dpg.add_spacer(height=3)
                    with dpg.group(horizontal=True):
                        dpg.add_spacer(width=656, show=True)
                        with dpg.group():
                            dpg.add_button(id='RunAnalysisBtn', label='Begin Analysis',callback=Gui._cb_run_analysis, user_data={'ctr':self}, enabled=False)
                        dpg.add_loading_indicator(id='LoadingIcon', style=1, radius=1.8, show=False)

            dpg.set_primary_window('MainWindow', True)

            dpg.setup_dearpygui()
            dpg.show_viewport()
        
            while self.exit != True and dpg.is_dearpygui_running() :
                tmp = dpg.get_value('VideoPosSlider')
                if(self._update_frame == True):
                    self._refresh_preview_frame()
                dpg.render_dearpygui_frame()
        except SystemError as e:
            LogManager.write_error_log(e)
        finally:
            dpg.destroy_context()

    def _cb_close_error_popup(sender, app_data, user_data):
        dpg.configure_item('ModalErrorPopup', show=False)
        user_data['ctr'].exit = True
        


    def _cb_cancel_exit(sender, app_data, user_data):
        dpg.configure_item('ModalConfirmExit', show=False)

    def _cb_save_and_quit(sender, app_data, user_data):
        save_success = Gui._cb_save(sender, app_data, user_data)
        if(save_success == True):
            Gui._cb_exit(sender, app_data, user_data)
        else:
            Gui._cb_cancel_exit(sender, app_data, user_data)

    def _cb_exit(sender, app_data, user_data):
        user_data['ctr'].exit = True

    def _cb_save(sender, app_data, user_data):
        controller = user_data['ctr']
        if(controller.report_filename == None or user_data['file-override'] == True):
            accepted_filetypes = [ ('Video Bites Report files', '*.g8r'), ('All files', '*.*')]
            filepath = filedialog.asksaveasfilename(initialdir=os.getcwd(), filetypes=accepted_filetypes, defaultextension='.g8r')
        else:
            filepath = controller.report_filename
        if(filepath != None and filepath != ''):
            file = open(filepath, 'w')
            controller.report_filename = filepath
            controller.has_saved = True

            src_video_filepath = None
            if(controller._analyzer.filepath != None):
                src_video_filepath = controller._analyzer.filepath
      
            encodable_results = []
            for result in controller._raw_report_results:
                if(result[2] == True):
                    encodable_results.append((result[0], result[1], 1))
                else:
                    encodable_results.append((result[0], result[1], 0))

            save_obj = {
                "src_file":controller._analyzer.filepath, 
                "frame_count":controller._frame_count,
                "fps":controller._fps,
                "frame_windows":controller._setting_ranges,
                "window_size":dpg.get_value('WindowSizeInput'),
                "point_value":dpg.get_value('PointValueInput'),
                "decay_rate":dpg.get_value('DecayRateInput'),
                "raw_report_results":encodable_results
            }
            with file:
                file.write(json.dumps(save_obj))
            file.close()
            return True
        else:
            return False
    
    def _cb_open(sender, app_data, user_data):
        try:
            controller = user_data['ctr']
            accepted_filetypes = [ ('Video Bites Report file', '*.g8r') ]
            report_filepath = filedialog.askopenfilename(initialdir=os.getcwd(), filetypes=accepted_filetypes)
            
            if(report_filepath != None and report_filepath != ''):
                Gui._clear_fields(controller)
                file = open(report_filepath)
                data = json.load(file)
                converted_tuples = []
                for json_array in data['frame_windows']:
                    converted_tuples.append((json_array[0], json_array[1]))

                for current_window in data['frame_windows']:
                    start_frame = current_window[0]
                    end_frame = current_window[1]
                    text = f"{start_frame}-{end_frame}"
                    with dpg.group(parent='SettingsContainer', horizontal=True):
                        controller._setting_ranges.append((start_frame, end_frame))
                        label = dpg.add_text(default_value=text)
                        edit_btn = dpg.add_button()
                        del_btn = dpg.add_button()
                        dpg.configure_item(edit_btn, label='Edit', callback=Gui._cb_add_setting,
                            user_data={
                                'ctr':user_data['ctr'],
                                'edit-tgt':label,
                                'range':(current_window[0], current_window[1]),
                                'label':label,
                                'edit-btn':edit_btn,
                                'del-btn':del_btn
                            }
                        )
                        dpg.configure_item(del_btn,label='Delete', callback=Gui._cb_delete_setting_button,
                            user_data={
                                'ctr':user_data['ctr'],
                                'self':dpg.get_item_parent(label),
                                'range':current_window
                            }
                        )
                controller.has_saved = True
                src_filepath = data['src_file']
            
                if (src_filepath != None and src_filepath != ''):
                    analyzer = controller._analyzer
                    if(controller._video != None):
                        controller._video.release()
                    
                    analyzer.set_filepath(src_filepath)
                    dpg.set_value('TgtFilepath', src_filepath)
                    dpg.delete_item('VideoPosSlider')
                    controller._video = cv2.VideoCapture(src_filepath)
                    num_frames = int(controller._video.get(cv2.CAP_PROP_FRAME_COUNT))
                    Gui._change_preview_frame(controller._video, 0)
                    controller._current_frame = 0
                    dpg.add_slider_int(
                        id='VideoPosSlider',
                        parent='PreviewSection',
                        min_value=1,
                        max_value=num_frames,
                        default_value=1,
                        width=529,
                        enabled=True,
                        callback=Gui._cb_frame_slider,
                        user_data={'ctr':controller}
                    )

                dpg.set_value('WindowSizeInput', data['window_size'])
                dpg.set_value('PointValueInput', data['point_value'])
                dpg.set_value('DecayRateInput', data['decay_rate'])
                for raw_result in data['raw_report_results']:
                    is_result_true = raw_result[2] == 1
                    controller._raw_report_results.append((raw_result[0], raw_result[1], is_result_true))
                controller._frame_count = data['frame_count']
                controller._fps = data['fps']
                if (len(controller._raw_report_results) > 0):
                    controller._process_raw_results()

                dpg.configure_item('RunAnalysisBtn', enabled=Gui._check_analysis_prereqs(user_data['ctr']))
        except Exception as e:
            LogManager.write_error_log(e)
            dpg.configure_item('ModalErrorPopup', show=True)
        except SystemError as e:
            LogManager.write_error_log(e)
            dpg.configure_item('ModalErrorPopup', show=True)
            
    def _cb_attempt_exit(sender, app_data, user_data):
        if(user_data['ctr'].has_saved != True):
            dpg.configure_item('ModalConfirmExit', show=True)
        else:
            Gui._cb_exit(sender, app_data, user_data)
    
    def _cb_frame_slider(sender, app_data, user_data):
        controller = user_data['ctr']
        if(controller._video != None):
            controller._current_frame = app_data
            controller._update_frame = True

    def _cb_add_setting(sender, app_data, user_data):
        edit_tgt = user_data.get('edit-tgt')
        if(edit_tgt != None):
            string = dpg.get_value(edit_tgt)
            index = string.find('-')
            start = int(string[:index])
            end = int(string[index+1:])
            dpg.set_value('NewSettingStartInput', start)
            dpg.set_value('NewSettingEndInput', end)
        dpg.configure_item('ModalNewSetting', show=True, pos=(250, 100), user_data=user_data)
        dpg.configure_item('NewSettingConfirmBtn', user_data=user_data)
        
    def _cb_confirm_new_setting_modal(sender, app_data, user_data):
        controller = user_data['ctr']
        is_data_valid = True
        setting_ranges = user_data.get('ctr')._setting_ranges
        edit_tgt = user_data.get('edit-tgt')
        prev_range = user_data.get('range')
        start_frame = dpg.get_value('NewSettingStartInput')
        end_frame = dpg.get_value('NewSettingEndInput')

        if (start_frame < 1):
            dpg.set_value('StartErrorText','Please enter a number greater than 0.')
            is_data_valid = False
        else:
            dpg.set_value('StartErrorText','')

        if (end_frame < 1):
            dpg.set_value('EndErrorText','Please enter a number greater than 0.')
            is_data_valid = False
        else:
            dpg.set_value('EndErrorText','')

        frame_overlap = False
        relevant_range = None

        for setting_range in setting_ranges:
            if (setting_range != prev_range
            and Gui._do_ranges_overlap((start_frame, end_frame), setting_range)):
                frame_overlap = True
                relevant_range = setting_range
                break

        if (is_data_valid and end_frame <= start_frame):
            dpg.set_value('NewSettingGeneralErrorText','End value must be greater than Start value.')
            is_data_valid = False
        elif(frame_overlap):
            dpg.set_value('NewSettingGeneralErrorText',f'Range overlaps with existing range ({relevant_range[0]}-{relevant_range[1]}).')
            is_data_valid = False
        else:
            dpg.set_value('NewSettingGeneralErrorText','')

        if(is_data_valid):
            current_range = (start_frame,end_frame)
            text = f"{start_frame}-{end_frame}"
            if(edit_tgt == None):
                with dpg.group(parent='SettingsContainer', horizontal=True):
                    user_data['ctr']._setting_ranges.append((start_frame, end_frame))
                    label = dpg.add_text(default_value=text)
                    edit_btn = dpg.add_button()
                    del_btn = dpg.add_button()
                    dpg.configure_item(edit_btn, label='Edit', callback=Gui._cb_add_setting,
                        user_data={
                            'ctr':user_data['ctr'],
                            'edit-tgt':label,
                            'range':current_range,
                            'label':label,
                            'edit-btn':edit_btn,
                            'del-btn':del_btn
                        }
                    )
                    dpg.configure_item(del_btn,label='Delete', callback=Gui._cb_delete_setting_button,
                        user_data={
                            'ctr':user_data['ctr'],
                            'self':dpg.get_item_parent(label),
                            'range':current_range
                        }
                    )
            else:
                setting_ranges.remove(prev_range)
                setting_ranges.append(current_range)
                label = user_data['label']
                dpg.set_value(label, text)
                edit_btn = user_data['edit-btn']
                del_btn = user_data['del-btn']
                dpg.configure_item(edit_btn, label='Edit', callback=Gui._cb_add_setting,
                    user_data={
                        'ctr':user_data['ctr'],
                        'edit-tgt':label,
                        'range':current_range,
                        'label':label,
                        'edit-btn':edit_btn,
                        'del-btn':del_btn
                    }
                )
                dpg.configure_item(del_btn,label='Delete', callback=Gui._cb_delete_setting_button,
                    user_data={
                        'ctr':user_data['ctr'],
                        'self':dpg.get_item_parent(label),
                        'range':current_range
                    }
                )
                
            is_ready = Gui._check_analysis_prereqs(user_data['ctr'])
            dpg.configure_item('RunAnalysisBtn', enabled=is_ready)
            Gui._cb_close_new_setting_modal(sender, app_data, user_data)
            controller.has_saved = False
        
    def _cb_close_new_setting_modal(sender, app_data, user_data):
        dpg.configure_item('ModalNewSetting', show=False, pos=(250, 100), user_data=user_data)
        dpg.configure_item('NewSettingConfirmBtn', user_data=user_data)
        dpg.set_value('NewSettingStartInput', 1)
        dpg.set_value('NewSettingEndInput', 1)
        dpg.set_value('StartErrorText','')
        dpg.set_value('EndErrorText','')
        dpg.set_value('NewSettingGeneralErrorText','')

    def _cb_delete_setting_button(sender, app_data, user_data):
        controller = user_data['ctr']
        group = user_data['self']
        children = dpg.get_item_children(group)[1]
        current_range = user_data['range']
        user_data['ctr']._setting_ranges.remove(current_range)
        for child in children:
            dpg.delete_item(child)
        dpg.delete_item(group)
        dpg.configure_item('RunAnalysisBtn', enabled=Gui._check_analysis_prereqs(user_data['ctr']))
        controller.has_saved = False

    def _cb_choose_src_vid(sender, app_data, user_data):
        controller = user_data['ctr']
        accepted_filetypes = [ ('MP4 video files', '*.mp4') ]
        filepath = filedialog.askopenfilename(initialdir=os.getcwd(), filetypes=accepted_filetypes)
        
        if (filepath != None and filepath != ''):
            analyzer = controller._analyzer
            if(controller._video != None):
                controller._video.release()
            
            analyzer.set_filepath(filepath)
            dpg.set_value('TgtFilepath', filepath)
            dpg.delete_item('VideoPosSlider')
            controller._video = cv2.VideoCapture(filepath)
            num_frames = int(controller._video.get(cv2.CAP_PROP_FRAME_COUNT))
            Gui._change_preview_frame(controller._video, 0)
            controller._current_frame = 0
            dpg.add_slider_int(
                id='VideoPosSlider',
                parent='PreviewSection',
                min_value=1,
                max_value=num_frames,
                default_value=1,
                width=529,
                enabled=True,
                callback=Gui._cb_frame_slider,
                user_data={'ctr':controller}
            )
        dpg.configure_item('RunAnalysisBtn', enabled=Gui._check_analysis_prereqs(user_data['ctr']))
        controller.has_saved = False

    def _cb_run_analysis(sender, app_data, user_data):
        controller = user_data['ctr']
        dpg.configure_item('LoadingIcon',show=True)
        dpg.configure_item('RunAnalysisBtn', enabled=False)
        dpg.configure_item('NewSettingBtn', enabled=False)
        dpg.configure_item('SrcBtn', enabled=False)
        frame_ranges = controller._setting_ranges
        controller._raw_report_results, controller._frame_count, controller._fps = controller._analyzer.run_analysis(frame_ranges)
                
        controller._process_raw_results()
        dpg.configure_item('LoadingIcon',show=False)
        dpg.configure_item('RunAnalysisBtn', enabled=True)
        dpg.configure_item('NewSettingBtn', enabled=True)
        dpg.configure_item('SrcBtn', enabled=True)
        controller.has_saved = False

        total_comments = 0

    def _process_raw_results(self):
        window_size = dpg.get_value('WindowSizeInput')
        point_score = dpg.get_value('PointValueInput')
        point_decay_rate = dpg.get_value('DecayRateInput')

        self._total_x_data = []
        self._total_y_data = []
        self._boxed_x_data = []
        self._boxed_y_data = []
        self._scored_x_data = []
        self._scored_y_data = []
        self._total_x_data.append(0)
        self._total_y_data.append(0)
        self._scored_x_data.append(0)
        self._scored_y_data.append(0)

        total_comments = 0
        running_count = 0

        aggregate_totals = {}
        base = 0
        while base < self._frame_count:
            aggregate_totals[base] = 0
            base += window_size
        
        frame_triggers = []
        for result in self._raw_report_results:
            frame_number = result[0]
            flag = result[2]

            if(flag == True):
                frame_triggers.append(frame_number)
                total_comments += 1
                self._total_x_data.append(frame_number)
                self._total_y_data.append(total_comments)
                aggregate_key = (int (frame_number / window_size)) * window_size
                aggregate_totals[aggregate_key] += 1

        score = 0
        for i in range(int(self._frame_count)):
            score = max(score - point_decay_rate / 10, 0)
            if i in frame_triggers:
                score += point_score
            self._scored_x_data.append(i)
            self._scored_y_data.append(score)

        self._total_x_data.append(self._frame_count)
        self._total_y_data.append(total_comments)
        dpg.configure_item('TotalSeries', x=self._total_x_data, y=self._total_y_data)    
        dpg.fit_axis_data('XAxisTotal')
        dpg.fit_axis_data('YAxisTotal')

        for x_val in aggregate_totals:
            self._boxed_x_data.append(x_val + window_size / 2)
            self._boxed_y_data.append(aggregate_totals[x_val])
     
        dpg.configure_item('BoxedSeries', x=self._boxed_x_data, y=self._boxed_y_data, label=f'Comments in {(window_size / self._fps):.2} Second Window', weight=window_size*0.95)
        dpg.fit_axis_data('XAxisBoxed')
        dpg.fit_axis_data('YAxisBoxed')

        dpg.configure_item('ScoredSeries', x=self._scored_x_data, y=self._scored_y_data)
        dpg.fit_axis_data('XAxisScored')
        dpg.fit_axis_data('YAxisScored')

    def _get_video_preview_frame(video_capture, frame_number):
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
        frame = video_capture.read()[1]
        shape = frame.shape

        scaled_h = 297
        scaled_w = 528

        preview_frame = cv2.resize(frame, dsize=(scaled_w, scaled_h), interpolation=cv2.INTER_CUBIC)
        return preview_frame

    def _refresh_preview_frame(self):
        self._update_frame = False
        Gui._change_preview_frame(self._video, self._current_frame)

    def _change_preview_frame(video, frame_number):
        frame = Gui._get_video_preview_frame(video, frame_number)
        texture_data = Gui._cv2_frame_to_dpg_texture_array(frame)
        
        if(dpg.does_item_exist('FramePreviewImage') == False):
            with dpg.texture_registry(show=False):
                width = frame.shape[1]
                height = frame.shape[0]
                if(dpg.does_item_exist('current-frame-preview')):
                    dpg.set_value('current-frame-preview', texture_data)
                else:
                    dpg.add_raw_texture(width=width, height=height, default_value=texture_data, format=dpg.mvFormat_Float_rgb, id='current-frame-preview')
            dpg.add_image('current-frame-preview', id='FramePreviewImage', parent='VideoPreview', pos=(0,0))
        else:
            dpg.set_value('current-frame-preview', texture_data)

    def _cv2_frame_to_dpg_texture_array(frame):
        unrolled_array = []
        height = frame.shape[0]
        width = frame.shape[1]

        texture = np.flip(frame, 2)
        texture = texture.ravel()
        texture = np.asfarray(texture, dtype='f')
        texture = np.true_divide(texture, 255.0)

        return texture

    def _do_ranges_overlap(left, right):
        if(right[0] < left[0] < right[1]
            or right[0] < left[1] < right[1]
            or left[0] < right[1] < left[1]):
            return True
        return False

    def _secs_to_tab_binding_title(num_total_seconds):
        num_seconds = int(num_total_seconds % 60)
        num_minutes = int(num_total_seconds / 60 % 60)
        num_hours = int(num_total_seconds / 3600)
        return f'tab-{num_hours:02}h{num_minutes:02}m{num_seconds:02}s-plot'

    def _check_analysis_prereqs(self):
        return len(self._setting_ranges) > 0 and self._analyzer.is_initialized()

    def _clear_fields(gui):
        gui._update_frame = False
        gui._current_frame = 0
        gui._analyzer = VideoAnalyzer()
        gui._target_windows = []
        gui._setting_ranges = []
        gui._report_results = {}
        gui._data_bindings = {}
        gui._video = None
        gui._slider = None
        gui.has_saved = True
        gui.report_filename = None
        gui.exit = False

        settings = dpg.get_item_children('SettingsContainer')[1]
        for setting in settings:
            dpg.configure_item(setting, show=False)
            dpg.delete_item(setting)
        dpg.delete_item('FramePreviewImage')
        dpg.configure_item('VideoPosSlider', min_value=0, max_value=0, default_value=0)
        dpg.configure_item('TgtFilepath', default_value='mp4 file not yet chosen')
