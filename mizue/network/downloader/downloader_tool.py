import concurrent.futures
import os
import time
from dataclasses import dataclass

from mizue.file import FileUtils
from mizue.network.downloader import DownloadStartEvent, ProgressEventArgs, DownloadCompleteEvent, Downloader, \
    DownloadEventType, DownloadFailureEvent
from mizue.printer import Printer
from mizue.printer.grid import ColumnSettings, Alignment, Grid, BorderStyle, CellRendererArgs
from mizue.progress import Progress, ProgressBarRendererArgs, SpinnerRendererArgs, LabelRendererArgs, \
    InfoSeparatorRendererArgs, InfoTextRendererArgs, PercentageRendererArgs


@dataclass
class DownloadReport:
    filename: str
    filesize: int
    url: str


class DownloaderTool:
    def __init__(self):
        self._report_data: list[DownloadReport] = []
        self._bulk_download_size = 0
        self._downloaded_count = 0
        self._total_download_count = 0
        self.progress: Progress | None = None

    def download(self, url: str, output_path: str):
        downloader = Downloader()
        downloader.add_event(DownloadEventType.STARTED, lambda event: self._on_download_start(event))
        downloader.add_event(DownloadEventType.PROGRESS, lambda event: self._on_download_progress(event))
        downloader.add_event(DownloadEventType.COMPLETED, lambda event: self._on_download_complete(event))
        downloader.add_event(DownloadEventType.FAILED, lambda event: self._on_download_failure(event))
        downloader.download(url, output_path)
        self._print_report()

    def download_bulk(self, urls: list[str], output_path: str, parallel: int = 4):
        self.progress = Progress(start=0, end=len(urls), value=0)
        self.progress.info_separator_renderer = self._info_separator_renderer
        self.progress.info_text_renderer = self._info_text_renderer
        self.progress.label_renderer = self._label_renderer
        self.progress.percentage_renderer = self._percentage_renderer
        self.progress.progress_bar_renderer = self._progress_bar_renderer
        self.progress.spinner_renderer = self._spinner_renderer
        self.progress.label = "Downloading: "
        self.progress.start()
        self._downloaded_count = 0
        self._total_download_count = len(urls)
        download_dict = {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            try:
                responses: list[concurrent.futures.Future] = []
                downloader = Downloader()
                downloader.add_event(DownloadEventType.PROGRESS,
                                     lambda event: self._on_bulk_download_progress(event, download_dict))
                downloader.add_event(DownloadEventType.COMPLETED,
                                        lambda event: self._on_bulk_download_complete(event))
                downloader.add_event(DownloadEventType.FAILED, lambda event: self._on_bulk_download_failed(event))
                for url in list(set(urls)):
                    responses.append(executor.submit(downloader.download, url, output_path))
                for response in concurrent.futures.as_completed(responses):
                    self._downloaded_count += 1
                    self.progress.update_value(self._downloaded_count)
                    self.progress.set_info(self._get_bulk_progress_info(download_dict))
                executor.shutdown(wait=True)
            except KeyboardInterrupt:
                downloader.close()
                self.progress.stop()
                Printer.warning(f"{os.linesep}Keyboard interrupt detected. Cleaning up...")
                executor.shutdown(wait=False, cancel_futures=True)
        self.progress.stop()
        self._print_report()

    @staticmethod
    def _get_basic_colored_text(text: str, percentage: float):
        if percentage < 25:
            return Printer.format_hex(text, '#ff0000')
        elif percentage < 50:
            return Printer.format_hex(text, '#ff8c00')
        elif percentage < 75:
            return Printer.format_hex(text, '#ffd700')
        else:
            return Printer.format_hex(text, '#00ff00')

    def _get_bulk_progress_info(self, download_dict: dict):
        file_progress_text = f'[{self._downloaded_count}/{self._total_download_count}]'
        size_text = FileUtils.get_readable_file_size(sum(download_dict.values()))
        return f'{file_progress_text} [{size_text}]'

    @staticmethod
    def _info_separator_renderer(args: InfoSeparatorRendererArgs):
        return Printer.format_hex(args.separator, '#FFCC75')

    @staticmethod
    def _info_text_renderer(args: InfoTextRendererArgs):
        return Printer.format_hex(args.text, '#FFCC75')
        # return DownloaderTool._get_basic_colored_text(args.text, args.percentage)

    @staticmethod
    def _label_renderer(args: LabelRendererArgs):
        return Printer.format_hex(args.label, '#FFCC75')

    def _on_bulk_download_complete(self, event: DownloadCompleteEvent):
        self._report_data.append(DownloadReport(event.filename, event.filesize, event.url))

    def _on_bulk_download_failed(self, event: DownloadFailureEvent):
        self._report_data.append(DownloadReport("", 0, event.url))

    def _on_bulk_download_progress(self, event: ProgressEventArgs, download_dict: dict):
        download_dict[event.url] = event.downloaded
        self.progress.set_info(self._get_bulk_progress_info(download_dict))

    def _on_download_complete(self, event: DownloadCompleteEvent):
        self.progress.update_value(event.filesize)
        downloaded_info = FileUtils.get_readable_file_size(event.filesize)
        filesize_info = FileUtils.get_readable_file_size(event.filesize)
        info = f'[{downloaded_info}/{filesize_info}]'
        self.progress.set_info(info)
        time.sleep(0.5)
        self.progress.stop()
        self._report_data.append(DownloadReport(event.filename, event.filesize, event.url))

    def _on_download_failure(self, event: DownloadFailureEvent):
        if isinstance(event.exception, KeyboardInterrupt):
            Printer.warning("Download has been cancelled by user.")
            print(os.linesep)
        if self.progress:
            self.progress.terminate()
        self._report_data.append(DownloadReport("", 0, event.url))

    def _on_download_progress(self, event: ProgressEventArgs):
        self.progress.update_value(event.downloaded)
        downloaded_info = FileUtils.get_readable_file_size(event.downloaded)
        filesize_info = FileUtils.get_readable_file_size(event.filesize)
        info = f'[{downloaded_info}/{filesize_info}]'
        self.progress.set_info(info)

    def _on_download_start(self, event: DownloadStartEvent):
        self.progress = Progress(start=0, end=event.filesize, value=0)
        self.progress.label = f'Downloading :: '
        self.progress.start()

    @staticmethod
    def _percentage_renderer(args: PercentageRendererArgs):
        return DownloaderTool._get_basic_colored_text("{:.2f}%".format(args.percentage), args.percentage)

    def _print_report(self):
        success_data = [report for report in self._report_data if report.filesize > 0]
        failed_data = [report for report in self._report_data if report.filesize == 0]
        row_index = 1
        success_grid_data = []
        for report in success_data:
            success_grid_data.append([row_index, report.filename, FileUtils.get_readable_file_size(report.filesize)])
            row_index += 1

        failed_grid_data = []
        for report in failed_data:
            failed_grid_data.append([row_index, report.url, 'Failed'])
            row_index += 1

        grid_columns: list[ColumnSettings] = [
            ColumnSettings(title='#', alignment=Alignment.RIGHT, renderer=lambda x: Printer.format_hex(x.cell, '#FFCC75')),
            ColumnSettings(title='Filename/URL', renderer=self._report_grid_file_column_cell_renderer),
            ColumnSettings(title='Filesize/Status', alignment=Alignment.RIGHT,
                           renderer=lambda x: Printer.format_hex(x.cell, '#FF0000')
                           if x.cell == 'Failed' else self._report_grid_cell_renderer(x))
        ]
        grid = Grid(grid_columns, success_grid_data + failed_grid_data)
        grid.border_style = BorderStyle.SINGLE
        grid.border_color = '#FFCC75'
        grid.cell_renderer = self._report_grid_cell_renderer
        print(os.linesep)
        grid.print()

    @staticmethod
    def _progress_bar_renderer(args: ProgressBarRendererArgs):
        return DownloaderTool._get_basic_colored_text(args.text, args.percentage)

    @staticmethod
    def _report_grid_cell_renderer(args: CellRendererArgs):
        if args.cell.endswith("KB"):
            return Printer.format_hex(args.cell, '#00a9ff')
        if args.cell.endswith("MB"):
            return Printer.format_hex(args.cell, '#d2309a')
        if args.is_header:
            return Printer.format_hex(args.cell, '#FFCC75')
        return args.cell

    @staticmethod
    def _report_grid_file_column_cell_renderer(args: CellRendererArgs):
        if args.is_header:
            return Printer.format_hex(args.cell, '#FFCC75')
        if args.cell.endswith(".jpg"):
            return Printer.format_rgb(args.cell, (0, 153, 153))
        if args.cell.endswith(".png"):
            return Printer.format_hex(args.cell, '#4440c0')
        return args.cell

    @staticmethod
    def _spinner_renderer(args: SpinnerRendererArgs):
        return DownloaderTool._get_basic_colored_text(args.spinner, args.percentage)