from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanelHeader
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect
from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty, NumericProperty
from kivy.clock import Clock
from pconsole import pconsole
from datetime import datetime
from kivy.logger import Logger
from .. import roboprinter
import sys
import os
import shutil
from scrollbox import ScrollBox, Scroll_Box_Even
from session_saver import session_saver
import traceback
import octoprint.filemanager
from common_screens import KeyboardInput, Modal_Question_No_Title
from connection_popup import Error_Popup, Warning_Popup
import octoprint.filemanager
from functools import partial

#This Classes express purpose is to explore the filesystem with a certain type of file in mind.
if sys.platform == "win32":
    USB_DIR = 'C:\\Users\\mauro\\AppData\\Roaming\\OctoPrint\\uploads\\USB'
    FILES_DIR = 'C:\\Users\\mauro\\AppData\\Roaming\\OctoPrint\\uploads'
else:
    USB_DIR = '/home/pi/.octoprint/uploads/USB'
    FILES_DIR = '/home/pi/.octoprint/uploads'
class File_Explorer(Scroll_Box_Even):
    
    def __init__(self, file_type, file_callback, enable_editing=False, **kwargs):
        
        
        if os.path.isdir(USB_DIR):
            try:
                if len(os.listdir(USB_DIR)) != 0:
                    self.has_usb_attached = True
                    session_saver.saved['usb_mounted'] = True
                else:
                    self.has_usb_attached = False
                    session_saver.saved['usb_mounted'] = False
            except Exception as e:
                self.has_usb_attached = False
                session_saver.saved['usb_mounted'] = False
        self.file_callback = file_callback
        self.enable_editing = enable_editing
        self.file_type = file_type
        self.oprint = roboprinter.printer_instance
        self.update_file_screen()

        #initialize scroll box even
        super(File_Explorer, self).__init__(self.file_buttons)



    def update_file_screen(self):
        self.files = self.oprint._file_manager.list_files(recursive=True)['local']
        session_saver.saved['current_files'] = self.files
        buttons = []
        folders = []


        for entry in self.files:
            if self.files[entry]['type'] == self.file_type:
                buttons.append(self.create_file_button(entry, self.files[entry]))
            elif self.files[entry]['type'] == 'folder':
                if entry != 'USB':
                    folders.append(self.create_folder_button(entry, self.files[entry]['path']))
                else:
                    if self.has_usb_attached:
                        folders.append(self.create_folder_button(entry, self.files[entry]['path'], USB=True))
                    #else there are no USB files to show so dont bother


        sorted_buttons = self.order_buttons_by_date(buttons)
        

        folders += sorted_buttons

        self.file_buttons = folders
        


    def make_folder_screen(self, files):
        buttons = []
        folders = []


        for entry in files:

            if files[entry]['type'] == self.file_type:
                path = files[entry]['path']
                if path.find('USB/') != -1:
                    buttons.append(self.create_file_button(entry, files[entry],is_usb = True))
                else:
                    buttons.append(self.create_file_button(entry, files[entry]))
            elif files[entry]['type'] == 'folder':
                folders.append(self.create_folder_button(entry, files[entry]['path']))


        sorted_buttons = self.order_buttons_by_date(buttons)

        #merge buttons with folders
        folders += sorted_buttons

        return Scroll_Box_Even(folders)


    def wait_for_screen_change(self, dt):
        current_tab = roboprinter.open_tab

        if current_tab != "file_screen":
            self.screen_lock = False
            self._update_file_screen()
            return False


    def order_buttons_by_date(self, button_array):

        date_array = []

        for button in button_array:
            button_raw_date = int(button.ids.date.text)
            button.ids.date.text = datetime.fromtimestamp(int(button.ids.date.text)).strftime("%b %d")
            date_array.append([button,button_raw_date])

        date_array.sort(key=lambda date: date[1], reverse=True)

        sorted_array = []

        for button in date_array:
            sorted_array.append(button[0])

        return sorted_array

    def create_file_button(self, filename, metadata, is_usb=False):
        date = str(metadata['date'])
        path = str(metadata['path'])

        return self.file_callback(filename=filename, date=date, path=path, is_usb = is_usb)

    def create_folder_button(self, folder_name, path, USB=False, **kwargs):
        # folder buttons need to be able to access their folders children
        split_path = path.split('/')
        if not USB:
            return FolderButton(folder_name, split_path, self.folder_screen, self.enable_editing)
        else:
            #We dont want users to delete their entire USB drive
            return FolderButton(folder_name, split_path, self.folder_screen, enable_editing = False)

    def folder_screen(self, name, path):
        _name = name
        back_destination = roboprinter.robo_screen()

        files = self._grab_files_in_folder(path)

        layout = self.make_folder_screen(files)

        roboprinter.back_screen(name=_name, title=_name, back_destination=back_destination, content=layout)

    def _grab_files_in_folder(self, path):
        folder = self.files
        
        # Every iteration makes the folder variable smaller
        for directory in path:
            folder = folder[directory]['children']

        return folder

class FolderButton(Button):
    name = StringProperty("error")
    path = ObjectProperty(None)
    file_function = ObjectProperty(None)
    edit_function = ObjectProperty(None)
    edit_icon = StringProperty('Icons/rounded_black.png')
    def __init__(self, name, path, callback_function, enable_editing = False, **kwargs):
        super(FolderButton, self).__init__()
        self.name = name
        self.path = path
        self.file_function = callback_function
        self.long_press = False
        self.enable_editing = enable_editing

        if self.enable_editing:
            self.edit_function = self.open_file_options
            self.edit_icon = "Icons/settings.png"
        else:
            self.edit_function = self.placeholder

    #this exist so we don't break the screen accidently
    def placeholder(self):
        pass

    def folder_on_press(self):
        if self.enable_editing:
            self.folder_clock = Clock.schedule_once(self.folder_clock_event, 1.0)
            Logger.info("Started clock")
        

    def folder_on_release(self):
        if not self.long_press:
            if self.enable_editing:
                self.folder_clock.cancel()
            self.file_function(self.name, self.path)
            
        else:
            self.long_press = False
            
    def folder_clock_event(self, dt):
        #self.long_press = True
        #FileOptions(self.name, self.path, folder = True)
        pass #re enable all this to enable file options

    def open_file_options(self):
        if self.enable_editing:
            FileOptions(self.name, self.path, folder = True)
        

#This Class is for creating/deleting files or folders. It will most commonly be used as a long press for Files and Folders
class FileOptions(BoxLayout):
    name = StringProperty('error')
    move_text = StringProperty(roboprinter.lang.pack['Files']['File_Options']['Move'])
    def __init__(self, name, path, folder = False, **kwargs):
        super(FileOptions, self).__init__()
        self.name = name
        self.path = path
        self.isFolder = folder
        if self.isFolder:
            self.move_text = roboprinter.lang.pack['Files']['File_Options']['MoveF']
        self.file_manager = roboprinter.printer_instance._file_manager
        back_destination = roboprinter.robo_screen()
        roboprinter.back_screen(name=self.name + "folder_options", 
                                title=roboprinter.lang.pack['Files']['File_Options']['Title'], 
                                back_destination=back_destination, 
                                content=self
                                )
    #Todo: Add a modal screen to ask the user if they are sure they want to delete this file/folder
    def delete(self):

        current_screen = roboprinter.robosm.current
        def confirm_delete():
            if self.isFolder:
                #delete the folder
                try:
                    path = "/".join(self.path)
                    #path = roboprinter.printer_instance._file_manager.path_on_disk('local', path)
                    roboprinter.printer_instance._file_manager.remove_folder('local', path, recursive=True)
                    roboprinter.robosm.go_back_to_main('files_tab')
                except Exception as e:
                    Logger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! "+ str(e))
                    traceback.print_exc()
    
                    ep = Error_Popup(roboprinter.lang.pack['Files']['Error']['Title'], roboprinter.lang.pack['Files']['Error']['Body'],callback=partial(roboprinter.robosm.go_back_to_main, tab='printer_status_tab'))
                    ep.open()
            #delete the file
            else:
                try:
                    path = roboprinter.printer_instance._file_manager.path_in_storage('local', self.path)
                    roboprinter.printer_instance._file_manager.remove_file('local', path)
                    roboprinter.robosm.go_back_to_main('files_tab')
                except Exception as e:
                    Logger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! "+ str(e))
                    traceback.print_exc()
    
                    ep = Error_Popup(roboprinter.lang.pack['Files']['Error']['Title'], roboprinter.lang.pack['Files']['Error']['Body'],callback=partial(roboprinter.robosm.go_back_to_main, tab='printer_status_tab'))
                    ep.open()
    
            Clock.schedule_once(self.update_files, 2)

        def cancel():
            roboprinter.robosm.current = current_screen

        #set variables for Folder or File
        title = roboprinter.lang.pack['Files']['Delete_File_Conf']['Title']
        body = roboprinter.lang.pack['Files']['Delete_File_Conf']['Body']
        pos = roboprinter.lang.pack['Files']['Delete_File_Conf']['positive']
        neg = roboprinter.lang.pack['Files']['Delete_File_Conf']['negative']
        if self.isFolder:
            title = roboprinter.lang.pack['Files']['Delete_Folder_Conf']['Title']
            body = roboprinter.lang.pack['Files']['Delete_Folder_Conf']['Body']


        #make confirmation screen
        content = Modal_Question_No_Title(body, 
                                          pos, 
                                          neg, 
                                          confirm_delete, 
                                          cancel)
    
        #make screen
        roboprinter.robosm._generate_backbutton_screen(name='delete_confirmation', 
                                                     title = title , 
                                                     back_destination=current_screen, 
                                                     content=content
                                                     )      
    


        

    def update_files(self,dt):
        if 'file_callback' in session_saver.saved:
            session_saver.saved['file_callback']()

            
            

    def add_folder(self):
        #find the current directory
        KeyboardInput(keyboard_callback = self.get_folder_name)

    def get_folder_name(self, folder_name):
        self.folder_name = folder_name

        #grab the current directory instead of a file or 1 folder deeper
        up1dir = ""
        if not self.isFolder:
            self.path = '/' + roboprinter.printer_instance._file_manager.path_in_storage('local', self.path)
            self.path = self.path.split('/')
            
        for dirs in range(0, len(self.path) -1):
            up1dir += '/' + self.path[dirs]
        up1dir += '/' + self.folder_name
        
           
        #TODO: detect if the name is already taken or not
        self.file_manager.add_folder('local',up1dir)

        #once finished go back to main
        roboprinter.robosm.go_back_to_main('files_tab')

    def move_object(self):
        if self.isFolder:
            Save_Local_File('/'.join(self.path), self.name, folder=True)
        else:
            #convert file path to local path
            self.path = '/' + roboprinter.printer_instance._file_manager.path_in_storage('local', self.path)
            self.path = self.path.split('/')
            Save_Local_File('/'.join(self.path), self.name)

class Save_Local_File():
    def __init__(self, local_path, name, folder=False, **kwargs):
        #super(Save_File, self).__init__()
        self.folder = folder
        self.path = local_path
        self.name = name
        self.files = roboprinter.printer_instance._file_manager.list_files(recursive=True)['local']
        layout = self.make_folder_screen(self.files)
        back_destination = str(roboprinter.robo_screen())
        Logger.info(back_destination)
        roboprinter.back_screen(name="local", 
                                title=roboprinter.lang.pack['Files']['Save_File']['Title'], 
                                back_destination=back_destination, 
                                content=layout,
                                cta = self.save,
                                icon = 'Icons/Slicer wizard icons/Save.png')

    def make_folder_screen(self, files):
        buttons = []
        folders = []

        for entry in files:
            if files[entry]['path'] != self.path:
                if files[entry]['type'] == 'folder':
                    #if the USB isn't mounted don't show it as an option
                    if entry == "USB":
                        if 'usb_mounted' in session_saver.saved:
                            if session_saver.saved['usb_mounted']:
                                folders.append(self.create_folder_button(entry, files[entry]['path']))
                    else:
                        folders.append(self.create_folder_button(entry, files[entry]['path']))

        return Scroll_Box_Even(folders)

    def create_folder_button(self, folder_name, path):
        # folder buttons need to be able to access their folders children
        split_path = path.split('/')
        return FolderButton(folder_name, split_path, self.folder_screen)

    def folder_screen(self, name, path):
        _name = name
        back_destination = str(roboprinter.robo_screen())
        Logger.info(back_destination)

        files = self._grab_files_in_folder(path)

        layout = self.make_folder_screen(files)

        roboprinter.back_screen(name="ROBOSAVE" + "/".join(path), 
                                title=_name, 
                                back_destination=back_destination, 
                                content=layout,
                                cta = self.save,
                                icon = 'Icons/Slicer wizard icons/Save.png')

    #have to add *args and **kwargs because of the backbutton screen
    def save(self, *args,**kwargs):
        self.wp = Warning_Popup(roboprinter.lang.pack['Files']['Warning']['Title'], roboprinter.lang.pack['Files']['Warning']['Body'])
        self.wp.open()

        Clock.schedule_once(self._save, 0)

    
    def _save(self, dt):
        save_dir = roboprinter.robo_screen()
        save_dir = save_dir.replace("ROBOSAVE", "")

        

        

        if save_dir == 'local':
            save_dir = FILES_DIR
            short_dir = 'local/'
        else:
            short_dir = save_dir + "/"
            save_dir = roboprinter.printer_instance._file_manager.path_on_disk('local', save_dir)

        file_path = roboprinter.printer_instance._file_manager.path_on_disk('local', self.path)


        try:
            Logger.info(file_path + " " + save_dir)
            
            shutil.move(file_path, save_dir)
            
        except Exception as e:
            Logger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! "+ str(e))
            traceback.print_exc()

            ep = Error_Popup(roboprinter.lang.pack['Files']['Move_Error']['Title'] , roboprinter.lang.pack['Files']['Move_Error']['Body'],callback=partial(roboprinter.robosm.go_back_to_main, tab='printer_status_tab'))
            ep.open()
        
        

        Logger.info('File Saved/Removed')
        roboprinter.robosm.go_back_to_main('files_tab')

        #add a 2 second delay for updating files
        Clock.schedule_once(self.update_files, 2)
        self.wp.dismiss()
        

    def update_files(self,dt):
        if 'file_callback' in session_saver.saved:
            session_saver.saved['file_callback']()


    def _grab_files_in_folder(self, path):
        folder = self.files
        
        # Every iteration makes the folder variable smaller
        for directory in path:
            folder = folder[directory]['children']

        return folder    


class Save_File():
    def __init__(self, file_path, meta_data=None, **kwargs):
        #super(Save_File, self).__init__()
        self.meta = meta_data
        self.temp_file_path = file_path
        self.files = roboprinter.printer_instance._file_manager.list_files(recursive=True)['local']
        layout = self.make_folder_screen(self.files)
        back_destination = str(roboprinter.robo_screen())
        Logger.info(back_destination)
        roboprinter.back_screen(name="local", 
                                title=roboprinter.lang.pack['Files']['Save_File']['Title'], 
                                back_destination=back_destination, 
                                content=layout,
                                cta = self.save,
                                icon = 'Icons/Slicer wizard icons/Save.png')

    def make_folder_screen(self, files):
        buttons = []
        folders = []

        for entry in files:
        
            if files[entry]['type'] == 'folder':
                #if the USB isn't mounted don't show it as an option
                if entry == "USB":
                    if 'usb_mounted' in session_saver.saved:
                        if session_saver.saved['usb_mounted']:
                            folders.append(self.create_folder_button(entry, files[entry]['path']))
                else:
                    folders.append(self.create_folder_button(entry, files[entry]['path']))

        return Scroll_Box_Even(folders)

    def create_folder_button(self, folder_name, path):
        # folder buttons need to be able to access their folders children
        split_path = path.split('/')
        return FolderButton(folder_name, split_path, self.folder_screen)

    def folder_screen(self, name, path):
        _name = name
        back_destination = str(roboprinter.robo_screen())

        files = self._grab_files_in_folder(path)

        layout = self.make_folder_screen(files)

        roboprinter.back_screen(name="ROBOSAVE" + "/".join(path), 
                                title=_name, 
                                back_destination=back_destination, 
                                content=layout,
                                cta = self.save,
                                icon = 'Icons/Slicer wizard icons/Save.png')

    #have to add *args and **kwargs because of the backbutton screen
    def save(self, usb = False, *args,**kwargs):
        if self.meta != None:
            self.save_meta()
        save_dir = roboprinter.robo_screen()
        Logger.info(save_dir)
        save_dir = save_dir.replace("ROBOSAVE", "")
        Logger.info(save_dir)

        filename = os.path.basename(self.temp_file_path)

        if save_dir == 'local':
            save_dir = FILES_DIR + "/"+ filename
            final_dir = save_dir
            counter = 0
            #don't overwrite an already saved file
            while os.path.isfile(final_dir):
                counter += 1
                final_dir = save_dir.replace(".gcode", "_" + str(counter) + ".gcode")
                
            short_dir = 'local/'
        else:
            short_dir = save_dir  + "/"
            save_dir = FILES_DIR + "/" + save_dir + "/"+ filename
            final_dir = save_dir
            counter = 0
            #dont overwrite an already saved file
            while os.path.isfile(final_dir):
                counter += 1
                final_dir = save_dir.replace(".gcode", "_" + str(counter) + ".gcode")
                


        if os.path.isfile(self.temp_file_path):
            #copy the file
            shutil.copyfile(self.temp_file_path, final_dir)
            #remove the temporary file if it is not from a USB drive
            if not usb:
                os.remove(self.temp_file_path)

            fit_filename = filename.replace(".gcode", "_" + str(counter))
            

            if len(fit_filename) > 24:
                fit_filename = "..." + fit_filename[len(fit_filename) - 24:]

            layout = Confirmation_Screen(roboprinter.lang.pack['Files']['Save_File']['Sub_Title'],  fit_filename + roboprinter.lang.pack['Files']['Save_File']['Body'], "Icons/Slicer wizard icons/check_icon.png", roboprinter.robosm.go_back_to_main)            
            sc = Screen(name = 'confirmation')
            sc.add_widget(layout)
            roboprinter.robosm.add_widget(sc)
            roboprinter.robosm.current = sc.name
            
        Logger.info('File Saved/Removed')
        #add a 2 second delay for updating files
        Clock.schedule_once(self.update_files, 2)
        

    def update_files(self,dt):
        if 'file_callback' in session_saver.saved:
            session_saver.saved['file_callback']()


    def save_meta(self):
        #append meta data to the end of a file
        if os.path.isfile(self.temp_file_path):
            with open(self.temp_file_path, "a") as file:
                file.write("\n\n") #skip two lines
                file.write(";Custom Meta Data from RoboLCD Written by Matt Pedler:\n")
                for meta in self.meta:
                    file.write("; " + str(meta) + " = " + str(self.meta[meta]) + "\n")

        return



    def meta_saver(self, dt):
        
        roboprinter.printer_instance._file_manager.set_additional_metadata( octoprint.filemanager.FileDestinations.LOCAL,
                                                                            self.npath ,
                                                                            'robo_data',
                                                                            self.meta,
                                                                            overwrite= True
                                                                            )
        local_meta = roboprinter.printer_instance._file_manager.get_metadata('local', self.npath)
        if local_meta != None:
            if 'robo_data' in local_meta:
                return False
            else:
                Logger.info("Still Saving")
        else:
            Logger.info("Still Saving")





    def _grab_files_in_folder(self, path):
        folder = self.files
        # Every iteration makes the folder variable smaller
        for directory in path:
            folder = folder[directory]['children']

        return folder
class Confirmation_Screen(BoxLayout):
    """docstring for Confirmation_Screen"""
    warning = StringProperty("Error")
    body_text = StringProperty("error")
    icon = StringProperty("Icons/button_pause_blank.png")
    button_function = ObjectProperty(None)
    def __init__(self, warning, body_text, icon, button_function):
        super(Confirmation_Screen, self).__init__()
        self.warning = warning
        self.body_text = body_text 
        self.icon = icon
        self.button_function = button_function
