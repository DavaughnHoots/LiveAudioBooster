import sys
import numpy as np
import sounddevice as sd
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider, QComboBox, QLabel, QPushButton, QMessageBox
from PyQt5.QtCore import Qt
import pyqtgraph as pg

class LiveAudioBooster(QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Live Audio Booster')

        self.setWindowTitle('Live Audio Booster')
        self.setGeometry(300, 300, 400, 200)  # Set window size and position

        vbox = QVBoxLayout()

        # Help Button
        self.help_button = QPushButton('Help')
        self.help_button.clicked.connect(self.show_help_dialog)
        vbox.addWidget(self.help_button)

        # In init_ui()
        self.status_label = QLabel('Status: Ready')
        vbox.addWidget(self.status_label)

        # Device List with Tooltip
        self.device_list = QComboBox()
        self.device_list.setToolTip('Select the virtual cable for audio input')
        vbox.addWidget(QLabel('Select Virtual Cable:'))
        vbox.addWidget(self.device_list)

        self.output_device_list = QComboBox()
        vbox.addWidget(QLabel('Select Output Device:'))
        vbox.addWidget(self.output_device_list)

        self.slider = QSlider(Qt.Horizontal)
        vbox.addWidget(QLabel('Volume (100% - 300%):'))
        vbox.addWidget(self.slider)
        
        # Start Button with Styling
        self.start_button = QPushButton('Start')
        self.start_button.setStyleSheet("QPushButton { background-color: green; color: white; }")
        vbox.addWidget(self.start_button)

        self.setLayout(vbox)

        self.slider.valueChanged.connect(self.change_volume)
        self.start_button.clicked.connect(self.start_audio_stream)
        self.device_list.currentIndexChanged.connect(self.update_output_devices)

         # Sampling Rate Selection
        self.sampling_rate_list = QComboBox()
        self.sampling_rate_list.addItems(['44100', '48000', '96000'])  # Common sampling rates
        vbox.addWidget(QLabel('Select Sampling Rate:'))
        vbox.addWidget(self.sampling_rate_list)

        # Waveform Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setYRange(-1, 1)  # Set Y range for audio waveform
        self.plot_data = self.plot_widget.plot()
        vbox.addWidget(self.plot_widget)

        self.test_and_populate_devices()
        self.slider.setRange(100, 300)        

    def find_output_device_index(self, output_device_name):
        device_info = sd.query_devices()
        return next(
            (
                device['index']
                for device in device_info
                if device['name'] == output_device_name
                and device['max_output_channels'] > 0
            ),
            None,
        )

    def test_and_populate_devices(self):
        self.input_devices = {}
        self.output_devices = {}
        device_info = sd.query_devices()
        output_device_name = "FxSound Speakers (FxSound Audio"
        output_device_index = self.find_output_device_index(output_device_name)

        if output_device_index is None:
            print("Output device not found.")
            return

        for device in device_info:
            device_name = device['name']
            device_index = device['index']
            if device['max_input_channels'] > 0:
                try:
                    with sd.Stream(device=(device_index, output_device_index)):
                        self.input_devices[device_name] = device_index
                except sd.PortAudioError as e:
                    print(f"Error with device {device_name}: {e}")
                except Exception as e:
                    print(f"Error with device {device_name}: {e}")
                    continue

            if device['max_output_channels'] > 0:
                self.output_devices[device_name] = device_index

        self.device_list.addItems(self.input_devices.keys())
        self.update_output_devices()

    def populate_devices(self):
        self.input_devices = {}
        self.output_devices = {}
        device_info = sd.query_devices()
        threshold = 0.000001  # Set an appropriate threshold for detecting audio

        for device in device_info:
            device_name = device['name']
            device_index = device['index']
            if device['max_input_channels'] > 0:
                # Measure input level to check if the device is active
                if self.measure_input_level(device_index) > threshold:
                    self.input_devices[device_name] = device_index
            if device['max_output_channels'] > 0:
                self.output_devices[device_name] = device_index

        self.device_list.addItems(self.input_devices.keys())
        self.update_output_devices()

    def update_output_devices(self):
        if input_device_name := self.device_list.currentText():
            input_device_index = self.input_devices[input_device_name]
            input_device_info = sd.query_devices(device=input_device_index, kind='input')
            input_channels = input_device_info['max_input_channels']

            self.output_device_list.clear()

            for device_name, device_index in self.output_devices.items():
                device_info = sd.query_devices(device=device_index, kind='output')
                if device_info['max_output_channels'] >= input_channels:
                    self.output_device_list.addItem(device_name)

    def change_volume(self, value):
        # Map the slider value (100-300) to a logarithmic scale
        min_value, max_value = 100, 300
        min_log, max_log = np.log10(1), np.log10(3)  # Logarithmic scale: 1 to 3
        log_value = np.log10(value / 100)
        scaled_value = (log_value - min_log) / (max_log - min_log)
        self.amplification_factor = scaled_value * 2 + 1  # Scale factor: 1 to 3

        # Update status label to show current amplification factor
        self.status_label.setText(f'Status: Volume set to {self.amplification_factor:.2f}x')


    def audio_callback(self, indata, outdata, frames, time, status):
        if status:
            print("Stream Error:", status)
            self.stop_stream()
            # update UI to show stream is stopped, put a message in the status bar, etc.
            self.start_button.setText('Start')
            self.status_label.setText(f'Status: Error - {status}')
            
        outdata[:] = indata * self.amplification_factor
        
        # Update Waveform Plot
        waveform = indata[:, 0]  # Assuming mono audio or using the first channel
        self.update_plot(waveform)
    
    def update_plot(self, data):
        self.plot_data.setData(data)
    
    def stop_stream(self):
        if hasattr(self, 'stream') and self.stream.active:
            self.stream.stop()
            self.start_button.setText('Start')
            self.status_label.setText('Status: Stopped')

    def start_audio_stream(self):
        try:
            if hasattr(self, 'stream') and self.stream.active:
                self.stream.stop()
                self.start_button.setText('Start')
            else:
                input_device_name = self.device_list.currentText()
                input_device_index = self.input_devices[input_device_name]
                input_device_info = sd.query_devices(device=input_device_index, kind='input')
                input_channels = input_device_info['max_input_channels']

                if output_device_name := self.output_device_list.currentText():
                    output_device_index = self.output_devices[output_device_name]

                    # Get selected sampling rate
                    sampling_rate = int(self.sampling_rate_list.currentText())

                    self.stream = sd.Stream(
                        samplerate=sampling_rate,
                        channels=(input_channels, input_channels),
                        dtype=np.float32,
                        latency='low',
                        callback=self.audio_callback,
                        device=(input_device_index, output_device_index),
                    )

                    self.stream.start()
                    self.start_button.setText('Stop')
        except Exception as e:
            print(e)
            self.start_button.setText('Start')
        self.status_label.setText('Status: Streaming')

    def closeEvent(self, event):
        self.stop_stream()
        event.accept()
        # update UI to show stream is stopped, put a message in the status bar, etc.
        self.start_button.setText('Start')
    
    def measure_input_level(self, device_index, duration=0.1):
        def callback(indata, frames, time, status):
            nonlocal level
            level = np.linalg.norm(indata) / frames

        level = 0
        try:
            with sd.InputStream(device=device_index, callback=callback):
                sd.sleep(int(duration * 1000))
        except sd.PortAudioError as e:
            print(f"Error with device {device_index}: {e}")
            return 0  # Or handle the error as appropriate
        return level

    def show_help_dialog(self):
            help_text = """
            <h1>Live Audio Booster Help</h1>
            <p><b>Setting up Virtual Cables:</b> To use a virtual cable...</p>
            <p><b>Choosing Devices:</b> Select the virtual cable...</p>
            <p><b>Volume Control:</b> Use the slider to adjust...</p>
            <p><b>Safety Warning:</b> Boosting volume above 100%...</p>
            """
            QMessageBox.information(self, "Help", help_text)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    live_audio_booster = LiveAudioBooster()
    live_audio_booster.show()
    sys.exit(app.exec_())
