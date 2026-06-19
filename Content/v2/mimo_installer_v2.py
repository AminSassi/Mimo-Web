"""
MiMo Installer v2.2 — Full GUI with Hardware Summary + Model Recommendations
Screens: Welcome → Location/Mode → Progress → Complete → Repair → Diagnostics
"""
import customtkinter as ctk
import subprocess
import os
import sys
import threading
import time
import json
import shutil
import zipfile
import socket
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from core import (
    MiMoLogger, get_version, get_build_number, get_build_date,
    get_log_dir, ensure_dirs, is_portable, version_dict,
    detect_all_gpus, select_best_gpu, detect_cuda_runtime,
    run_inference_smoke_test, get_gpu_info_dict,
    get_max_model_tier, get_model_recommendation, get_vram_warnings,
    MODEL_TIERS
)
from bootstrapper.MiMoBootstrapper import (
    HealthChecker, StateManager,
    run_cmd, refresh_path, is_admin, DEPENDENCIES
)

ctk.set_appearance_mode("light")

APP_VERSION = get_version()
BUILD_DATE = get_build_date()
BUILD_NUMBER = get_build_number()
VERSION_INFO = version_dict()

COLORS = {
    "bg": "#FAFBFC",
    "surface": "#FFFFFF",
    "surface_hover": "#F5F5F7",
    "border": "#E5E5EA",
    "border_light": "#F0F0F5",
    "text_primary": "#1D1D1F",
    "text_secondary": "#6E6E73",
    "text_tertiary": "#AEAEB2",
    "accent": "#007AFF",
    "accent_hover": "#0066D6",
    "accent_light": "#E8F4FD",
    "success": "#34C759",
    "success_light": "#E8F9ED",
    "warning": "#FF9500",
    "warning_light": "#FFF4E5",
    "error": "#FF3B30",
    "error_light": "#FFEDE8",
    "progress_bg": "#F0F0F5",
    "progress_fill": "#007AFF",
}


class ModernButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        defaults = {"height": 44, "corner_radius": 10, "font": ctk.CTkFont(size=14, weight="bold"), "cursor": "hand2"}
        defaults.update(kwargs)
        super().__init__(master, **defaults)


class MiMoInstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MiMo Installer v2.2")
        self.geometry("740x620")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])

        self.install_dir = os.path.join(os.path.expanduser("~"), "MiMo Auto")
        self.portable_mode = False
        self.running = False
        self.engine = None
        self.screens = []
        self.current_screen = 0

        self._build_screens()
        self._detect_hardware()
        self._show_screen(0)

    def _detect_hardware(self):
        self.gpu_info = get_gpu_info_dict()
        self.model_rec = get_model_recommendation(
            self.gpu_info["total_vram_gb"], self.gpu_info["free_vram_gb"]
        )
        self.vram_warnings = get_vram_warnings(
            self.gpu_info["total_vram_gb"], self.gpu_info["free_vram_gb"]
        )

    def _build_screens(self):
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.screens = [
            self._build_welcome(),
            self._build_location(),
            self._build_progress(),
            self._build_complete(),
            self._build_repair(),
            self._build_diagnostics(),
        ]
        version_bar = ctk.CTkLabel(self, text=f"MiMo Auto v{APP_VERSION} \u00b7 Build {BUILD_NUMBER} \u00b7 {BUILD_DATE}",
                                   font=ctk.CTkFont(size=10), text_color=COLORS["text_tertiary"])
        version_bar.pack(side="bottom", pady=(0, 6))

    def _make_card(self, parent):
        return ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=16,
                           border_width=1, border_color=COLORS["border"])

    def _show_screen(self, idx):
        for s in self.screens:
            s.pack_forget()
        self.current_screen = idx
        self.screens[idx].pack(fill="both", expand=True)

    def _build_welcome(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=30).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=30)

        logo = ctk.CTkFrame(inner, fg_color=COLORS["accent_light"], width=72, height=72, corner_radius=18)
        logo.pack(pady=(0, 14))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="M", font=ctk.CTkFont(size=32, weight="bold"),
                    text_color=COLORS["accent"]).pack(expand=True)

        ctk.CTkLabel(inner, text="Install MiMo Auto", font=ctk.CTkFont(size=26, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(pady=(0, 4))
        ctk.CTkLabel(inner, text="AI-powered coding assistant \u2014 runs locally on your GPU",
                    font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"]).pack(pady=(0, 20))

        features_frame = ctk.CTkFrame(inner, fg_color="transparent")
        features_frame.pack(fill="x", pady=(0, 20))
        for feat in ["Auto-detects & installs Node.js, Git, npm",
                     "Self-healing: auto-repairs on every launch",
                     "Portable mode available (no system changes)",
                     "Diagnostic export for troubleshooting"]:
            row = ctk.CTkFrame(features_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="  \u2713  ", font=ctk.CTkFont(size=13),
                        text_color=COLORS["success"]).pack(side="left")
            ctk.CTkLabel(row, text=feat, font=ctk.CTkFont(size=12),
                        text_color=COLORS["text_secondary"]).pack(side="left")

        hw_frame = self._make_card(inner)
        hw_frame.pack(fill="x", pady=(0, 16))
        hw_inner = ctk.CTkFrame(hw_frame, fg_color="transparent")
        hw_inner.pack(padx=16, pady=12, fill="x")

        ctk.CTkLabel(hw_inner, text="Your Hardware", font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))

        gpu = self.gpu_info
        if gpu["vendor"] == "NVIDIA":
            hw_lines = [
                (f"GPU: {gpu['model']}", COLORS["text_primary"]),
                (f"VRAM: {gpu['total_vram_gb']} GB ({gpu['free_vram_gb']} GB free)", COLORS["text_primary"]),
                (f"Driver: {gpu['driver_version']}", COLORS["text_primary"]),
                (f"CUDA: {'Supported' if gpu['cuda_available'] else 'Not detected'}",
                 COLORS["success"] if gpu["cuda_available"] else COLORS["error"]),
            ]
        else:
            hw_lines = [
                ("GPU: No NVIDIA GPU detected", COLORS["error"]),
                ("CUDA: Not available", COLORS["error"]),
                ("MiMo requires an NVIDIA GPU with CUDA support", COLORS["warning"]),
            ]

        for text, color in hw_lines:
            row = ctk.CTkFrame(hw_inner, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text="  \u2022  ", font=ctk.CTkFont(size=11),
                        text_color=COLORS["text_tertiary"]).pack(side="left")
            ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=11),
                        text_color=color).pack(side="left")

        if self.model_rec["recommended"]:
            rec_frame = ctk.CTkFrame(hw_inner, fg_color=COLORS["success_light"], corner_radius=6)
            rec_frame.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(rec_frame,
                text=f"  \u2713  {self.model_rec['message']}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["success"]).pack(padx=10, pady=6, anchor="w")
        elif gpu["vendor"] == "NVIDIA":
            warn_frame = ctk.CTkFrame(hw_inner, fg_color=COLORS["warning_light"], corner_radius=6)
            warn_frame.pack(fill="x", pady=(8, 0))
            ctk.CTkLabel(warn_frame,
                text=f"  \u26a0  {self.model_rec['message']}",
                font=ctk.CTkFont(size=11),
                text_color=COLORS["warning"]).pack(padx=10, pady=6, anchor="w")

        if self.vram_warnings:
            warn_frame = ctk.CTkFrame(hw_inner, fg_color=COLORS["warning_light"], corner_radius=6)
            warn_frame.pack(fill="x", pady=(6, 0))
            for w in self.vram_warnings[:2]:
                ctk.CTkLabel(warn_frame, text=f"  \u2022  {w}",
                    font=ctk.CTkFont(size=10), text_color=COLORS["warning"]).pack(padx=10, pady=1, anchor="w")

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")

        ModernButton(btn_frame, text="Begin Installation", fg_color=COLORS["accent"],
                    hover_color=COLORS["accent_hover"], command=lambda: self._show_screen(1)).pack(side="right")
        ModernButton(btn_frame, text="Repair", width=80, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["success"],
                    border_width=1, border_color=COLORS["success"],
                    command=lambda: self._show_screen(4)).pack(side="right", padx=(0, 8))
        ModernButton(btn_frame, text="Diagnostics", width=100, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["text_secondary"],
                    border_width=1, border_color=COLORS["border"],
                    command=lambda: self._show_screen(5)).pack(side="right", padx=(0, 8))

        return screen

    def _build_location(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=40).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=30)

        ctk.CTkLabel(inner, text="Installation Settings", font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 16))

        mode_label = ctk.CTkLabel(inner, text="Installation Mode", font=ctk.CTkFont(size=14, weight="bold"),
                                  text_color=COLORS["text_primary"])
        mode_label.pack(anchor="w", pady=(0, 6))

        mode_frame = ctk.CTkFrame(inner, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 16))

        self.mode_var = ctk.StringVar(value="full")

        full_card = ctk.CTkFrame(mode_frame, fg_color=COLORS["bg"], corner_radius=10,
                                 border_width=2, border_color=COLORS["accent"], cursor="hand2")
        full_card.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkRadioButton(full_card, text="Full Install", variable=self.mode_var, value="full",
                          font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"],
                          border_color=COLORS["accent"], hover_color=COLORS["accent"],
                          command=self._on_mode_change).pack(padx=14, pady=(10, 2), anchor="w")
        ctk.CTkLabel(full_card, text="System integration, shortcuts, auto-repair",
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(padx=14, pady=(0, 10), anchor="w")

        portable_card = ctk.CTkFrame(mode_frame, fg_color=COLORS["bg"], corner_radius=10,
                                     border_width=2, border_color=COLORS["border"], cursor="hand2")
        portable_card.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.portable_radio = ctk.CTkRadioButton(portable_card, text="Portable Mode", variable=self.mode_var, value="portable",
                          font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"],
                          border_color=COLORS["accent"], hover_color=COLORS["accent"],
                          command=self._on_mode_change)
        self.portable_radio.pack(padx=14, pady=(10, 2), anchor="w")
        ctk.CTkLabel(portable_card, text="No system changes, self-contained folder",
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(padx=14, pady=(0, 10), anchor="w")

        path_label = ctk.CTkLabel(inner, text="Install Location", font=ctk.CTkFont(size=14, weight="bold"),
                                  text_color=COLORS["text_primary"])
        path_label.pack(anchor="w", pady=(0, 6))

        path_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=10,
                                 border_width=1, border_color=COLORS["border"])
        path_frame.pack(fill="x", pady=(0, 12))
        self.path_label = ctk.CTkLabel(path_frame, text=self.install_dir,
                                      font=ctk.CTkFont(family="Consolas", size=12),
                                      text_color=COLORS["text_primary"])
        self.path_label.pack(side="left", padx=14, pady=10)
        ModernButton(path_frame, text="Change...", width=80, height=30, font=ctk.CTkFont(size=12),
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border"],
                    command=self._pick_folder).pack(side="right", padx=10, pady=10)

        disk_ok, free_gb = self._check_disk()
        ctk.CTkLabel(inner, text=f"{free_gb:.1f} GB available on C:\\",
                    font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 20))

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")
        ModernButton(btn_frame, text="Install", width=120, fg_color=COLORS["accent"],
                    hover_color=COLORS["accent_hover"], command=self._start_install).pack(side="right")
        ModernButton(btn_frame, text="Back", width=80, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["text_primary"],
                    border_width=1, border_color=COLORS["border"],
                    command=lambda: self._show_screen(0)).pack(side="right", padx=(0, 8))

        return screen

    def _build_progress(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=35).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=30)

        self.progress_title = ctk.CTkLabel(inner, text="Installing MiMo Auto",
                                          font=ctk.CTkFont(size=22, weight="bold"),
                                          text_color=COLORS["text_primary"])
        self.progress_title.pack(anchor="w", pady=(0, 4))

        self.progress_subtitle = ctk.CTkLabel(inner, text="This may take a few minutes",
                                             font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"])
        self.progress_subtitle.pack(anchor="w", pady=(0, 18))

        self.progress_bar_bg = ctk.CTkFrame(inner, fg_color=COLORS["progress_bg"], height=6, corner_radius=3)
        self.progress_bar_bg.pack(fill="x", pady=(0, 4))
        self.progress_bar_bg.pack_propagate(False)
        self.progress_bar_fill = ctk.CTkFrame(self.progress_bar_bg, fg_color=COLORS["progress_fill"], corner_radius=3)
        self.progress_bar_fill.place(relx=0, rely=0, relwidth=0, relheight=1)

        eta_frame = ctk.CTkFrame(inner, fg_color="transparent")
        eta_frame.pack(fill="x", pady=(2, 12))
        self.progress_pct = ctk.CTkLabel(eta_frame, text="0%", font=ctk.CTkFont(size=11), text_color=COLORS["text_tertiary"])
        self.progress_pct.pack(side="left")
        self.progress_eta = ctk.CTkLabel(eta_frame, text="Estimating...", font=ctk.CTkFont(size=11), text_color=COLORS["text_tertiary"])
        self.progress_eta.pack(side="right")

        self.log_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                      border_width=1, border_color=COLORS["border_light"])
        self.log_frame.pack(fill="x")
        self.log_box = ctk.CTkTextbox(self.log_frame, font=ctk.CTkFont(family="Consolas", size=11),
                                      fg_color="transparent", text_color=COLORS["text_secondary"],
                                      border_width=0, height=100, state="disabled")
        self.log_box.pack(padx=12, pady=10, fill="x")

        self.cancel_btn = ModernButton(inner, text="Cancel", width=80,
                                      fg_color=COLORS["surface"], hover_color=COLORS["error_light"],
                                      text_color=COLORS["error"], border_width=1, border_color=COLORS["border"],
                                      command=self._cancel_install)
        self.cancel_btn.pack(anchor="e", pady=(12, 0))

        return screen

    def _build_complete(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=25).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=28)

        self.complete_icon_frame = ctk.CTkFrame(inner, fg_color=COLORS["success_light"], width=64, height=64, corner_radius=32)
        self.complete_icon_frame.pack(pady=(0, 10))
        self.complete_icon_frame.pack_propagate(False)
        self.complete_icon_label = ctk.CTkLabel(self.complete_icon_frame, text="\u2713",
                    font=ctk.CTkFont(size=28, weight="bold"), text_color=COLORS["success"])
        self.complete_icon_label.pack(expand=True)

        self.complete_title = ctk.CTkLabel(inner, text="Installation Complete",
                                          font=ctk.CTkFont(size=24, weight="bold"), text_color=COLORS["text_primary"])
        self.complete_title.pack(pady=(0, 4))

        self.complete_subtitle = ctk.CTkLabel(inner, text="MiMo Auto is ready to use",
                                             font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"])
        self.complete_subtitle.pack(pady=(0, 8))

        self.summary_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                         border_width=1, border_color=COLORS["border_light"])
        self.summary_items = {}
        for key, label in [("nodejs", "Node.js"), ("git", "Git"), ("mimo", "MiMo")]:
            row = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            icon = ctk.CTkLabel(row, text="\u2713", font=ctk.CTkFont(size=12, weight="bold"),
                               text_color=COLORS["success"], width=20)
            icon.pack(side="left")
            name_lbl = ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                                   text_color=COLORS["text_primary"], width=80, anchor="w")
            name_lbl.pack(side="left")
            ver_lbl = ctk.CTkLabel(row, text="...", font=ctk.CTkFont(size=11), text_color=COLORS["text_tertiary"])
            ver_lbl.pack(side="left", padx=(4, 0))
            self.summary_items[key] = {"icon": icon, "ver": ver_lbl}

        self.complete_error_box = ctk.CTkFrame(inner, fg_color=COLORS["error_light"], corner_radius=8)
        self.complete_error_label = ctk.CTkLabel(self.complete_error_box, text="",
                                                font=ctk.CTkFont(size=11), text_color=COLORS["error"],
                                                wraplength=420, justify="left")
        self.complete_error_label.pack(padx=14, pady=10, anchor="w")

        self.validation_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                            border_width=1, border_color=COLORS["border_light"])
        self.validation_items = {}
        for check_name in ["GPU detected", "CUDA available", "Model path writable", "Inference test"]:
            row = ctk.CTkFrame(self.validation_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            icon = ctk.CTkLabel(row, text="...", font=ctk.CTkFont(size=11), width=20)
            icon.pack(side="left")
            lbl = ctk.CTkLabel(row, text=check_name, font=ctk.CTkFont(size=11),
                              text_color=COLORS["text_secondary"])
            lbl.pack(side="left")
            self.validation_items[check_name] = {"icon": icon, "label": lbl}

        self.tips_frame = ctk.CTkFrame(inner, fg_color=COLORS["accent_light"], corner_radius=8)
        self.tips_label = ctk.CTkLabel(self.tips_frame,
            text="Quick start:\n  mimo web       \u2014 Open web UI\n  mimo --version \u2014 Check version\n  mimo help      \u2014 Show all commands",
            font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text_primary"], justify="left")
        self.tips_label.pack(padx=14, pady=10, anchor="w")

        self.complete_btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        self.complete_btn_frame.pack(fill="x", pady=(12, 0))

        self.launch_btn = ModernButton(self.complete_btn_frame, text="Launch MiMo (Recommended)", width=200,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._launch_mimo)
        self.close_btn = ModernButton(self.complete_btn_frame, text="Close", width=80,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border"],
                    command=self.destroy)
        self.retry_btn = ModernButton(self.complete_btn_frame, text="Retry", width=80,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                    command=lambda: self._show_screen(0))
        self.copy_err_btn = ModernButton(self.complete_btn_frame, text="Copy Error", width=90,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
                    command=self._copy_error)
        self.open_logs_btn = ModernButton(self.complete_btn_frame, text="Open Logs", width=90,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
                    command=self._open_logs)
        self.export_btn = ModernButton(self.complete_btn_frame, text="Export Report", width=110,
                    fg_color=COLORS["surface"], hover_color=COLORS["surface_hover"],
                    text_color=COLORS["text_secondary"], border_width=1, border_color=COLORS["border"],
                    command=self._pick_export_path)

        return screen

    def _build_repair(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=40).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=30)

        ctk.CTkLabel(inner, text="Repair Installation", font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(inner, text="Auto-detect and fix issues with your MiMo installation.",
                    font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 16))

        self.repair_status = ctk.CTkLabel(inner, text="",
                                         font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"],
                                         wraplength=500, justify="left")
        self.repair_status.pack(anchor="w", pady=(0, 16))

        self.repair_log_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                             border_width=1, border_color=COLORS["border_light"])
        self.repair_log_frame.pack(fill="x", pady=(0, 16))
        self.repair_log_box = ctk.CTkTextbox(self.repair_log_frame,
            font=ctk.CTkFont(family="Consolas", size=11), fg_color="transparent",
            text_color=COLORS["text_secondary"], border_width=0, height=120, state="disabled")
        self.repair_log_box.pack(padx=12, pady=10, fill="x")

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")
        self.repair_start_btn = ModernButton(btn_frame, text="Run Repair", width=120, fg_color=COLORS["success"],
                    hover_color="#2DA44E", command=self._start_repair)
        self.repair_start_btn.pack(side="right")
        ModernButton(btn_frame, text="Back", width=80, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["text_primary"],
                    border_width=1, border_color=COLORS["border"],
                    command=lambda: self._show_screen(0)).pack(side="right", padx=(0, 8))

        return screen

    def _build_diagnostics(self):
        screen = ctk.CTkFrame(self.container, fg_color="transparent")
        ctk.CTkFrame(screen, fg_color="transparent", height=40).pack()

        card = self._make_card(screen)
        card.pack(padx=40, fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=40, pady=30)

        ctk.CTkLabel(inner, text="System Diagnostics", font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(inner, text="Export a diagnostic report for troubleshooting.",
                    font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 16))

        self.diag_status = ctk.CTkLabel(inner, text="Click 'Export Report' to generate a diagnostic ZIP.",
                                       font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"],
                                       wraplength=500, justify="left")
        self.diag_status.pack(anchor="w", pady=(0, 16))

        self.diag_log_frame = ctk.CTkFrame(inner, fg_color=COLORS["bg"], corner_radius=8,
                                           border_width=1, border_color=COLORS["border_light"])
        self.diag_log_frame.pack(fill="x", pady=(0, 16))
        self.diag_log_box = ctk.CTkTextbox(self.diag_log_frame,
            font=ctk.CTkFont(family="Consolas", size=11), fg_color="transparent",
            text_color=COLORS["text_secondary"], border_width=0, height=120, state="disabled")
        self.diag_log_box.pack(padx=12, pady=10, fill="x")

        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x")
        self.diag_export_btn = ModernButton(btn_frame, text="Export Report", width=120, fg_color=COLORS["accent"],
                    hover_color=COLORS["accent_hover"], command=self._export_diagnostic)
        self.diag_export_btn.pack(side="right")
        ModernButton(btn_frame, text="Back", width=80, fg_color=COLORS["surface"],
                    hover_color=COLORS["surface_hover"], text_color=COLORS["text_primary"],
                    border_width=1, border_color=COLORS["border"],
                    command=lambda: self._show_screen(0)).pack(side="right", padx=(0, 8))

        return screen

    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "portable":
            self.portable_mode = True
            self.install_dir = os.path.join(os.path.expanduser("~"), "MiMo Auto Portable")
        else:
            self.portable_mode = False
            self.install_dir = os.path.join(os.path.expanduser("~"), "MiMo Auto")
        self.path_label.configure(text=self.install_dir)

    def _pick_folder(self):
        try:
            from tkinter import filedialog
            folder = filedialog.askdirectory(initialdir=self.install_dir)
            if folder:
                self.install_dir = folder
                self.path_label.configure(text=folder)
        except Exception:
            pass

    def _check_disk(self):
        try:
            usage = shutil.disk_usage("C:\\")
            free_gb = usage.free / (1024 ** 3)
            return free_gb >= 2, free_gb
        except Exception:
            return False, 0

    def _set_progress(self, pct, text=None):
        def _update():
            w = max(pct / 100, 0.01)
            self.progress_bar_fill.place(relx=0, rely=0, relwidth=w, relheight=1)
            self.progress_pct.configure(text=f"{int(pct)}%")
            if text:
                self.progress_subtitle.configure(text=text)
        self.after(0, _update)

    def _append_log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log_progress(self, msg):
        self.after(0, self._append_log, msg)

    def _start_install(self):
        if self.running:
            return
        self.running = True
        self._show_screen(2)
        self.progress_title.configure(text="Installing MiMo Auto")
        self.summary_frame.pack_forget()
        self.tips_frame.pack_forget()
        self.complete_error_box.pack_forget()
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=self._run_install, daemon=True).start()

    def _start_repair(self):
        if self.running:
            return
        self.running = True
        self.repair_start_btn.configure(state="disabled", text="Repairing...")
        threading.Thread(target=self._run_repair, daemon=True).start()

    def _cancel_install(self):
        if self.running:
            self.running = False
            self._log_progress("Cancelling...")

    def _run_install(self):
        try:
            start_time = time.time()
            self._log_progress("MiMo Installer v2.0")
            self._set_progress(5, "Checking system requirements...")

            if not is_admin():
                self._log_progress("ERROR: Administrator privileges required")
                self.after(1000, lambda: self._finish(False, "Administrator Required",
                    "Right-click MiMo Installer and select 'Run as administrator'."))
                return

            self._log_progress("System check passed")
            self._set_progress(15, "Detecting dependencies...")
            self._log_progress("Scanning for Node.js, Git, npm...")

            logger = Logger(self.install_dir)
            checker = HealthChecker(self.install_dir, logger)
            issues = checker.health_check()

            if issues:
                self._set_progress(30, "Installing missing dependencies...")
                self._log_progress(f"Found {len(issues)} issue(s), installing...")
                checker.auto_repair(issues, self._log_progress)
                issues = checker.health_check()

            self._set_progress(70, "Validating installation...")
            self._log_progress("\nValidating all components...")

            state = StateManager(self.install_dir)
            state.state["portable"] = self.portable_mode
            if self.portable_mode:
                flag_path = os.path.join(self.install_dir, PORTABLE_FLAG)
                try:
                    Path(flag_path).touch()
                except Exception:
                    pass
            state.mark_installed()
            state.increment_launches()
            state.save()

            self._set_progress(90, "Saving logs...")
            logger.save("install")

            elapsed = time.time() - start_time
            self._log_progress(f"\nInstallation complete ({int(elapsed)}s)")

            self._set_progress(100, "Complete")
            self.after(500, lambda: self._finish(True, "Installation Complete"))
            threading.Thread(target=self._run_validation, daemon=True).start()
        except Exception as e:
            self._log_progress(f"\nError: {e}")
            self.after(1000, lambda err=str(e): self._finish(False, "Installation Failed", err))

    def _run_repair(self):
        try:
            self.after(0, lambda: self.repair_log_box.configure(state="normal"))
            self.after(0, lambda: self.repair_log_box.delete("1.0", "end"))
            self.after(0, lambda: self.repair_log_box.configure(state="disabled"))

            def log_repair(msg):
                self.after(0, lambda: (
                    self.repair_log_box.configure(state="normal"),
                    self.repair_log_box.insert("end", msg + "\n"),
                    self.repair_log_box.see("end"),
                    self.repair_log_box.configure(state="disabled")
                ))

            self.after(0, lambda: self.repair_status.configure(text="Checking system..."))
            log_repair("Running health check...")

            logger = Logger(self.install_dir)
            checker = HealthChecker(self.install_dir, logger)
            issues = checker.health_check()

            if not issues:
                self.after(0, lambda: self.repair_status.configure(
                    text="All components healthy. No repairs needed.", text_color=COLORS["success"]))
                log_repair("No issues found")
                self.after(0, lambda: self.repair_start_btn.configure(state="normal", text="Run Repair"))
                self.running = False
                return

            self.after(0, lambda: self.repair_status.configure(
                text=f"Found {len(issues)} issue(s). Repairing...", text_color=COLORS["warning"]))
            log_repair(f"Issues: {', '.join(issues)}")

            repaired = checker.auto_repair(issues, log_repair)

            remaining = checker.health_check()
            logger.save("repair")

            if not remaining:
                self.after(0, lambda: self.repair_status.configure(
                    text="Repair complete! All issues resolved.", text_color=COLORS["success"]))
                log_repair("All issues repaired")
            else:
                self.after(0, lambda r=remaining: self.repair_status.configure(
                    text=f"Remaining issues: {', '.join(r)}. A reboot may be required.",
                    text_color=COLORS["warning"]))
                log_repair(f"Remaining: {remaining}")

            self.after(0, lambda: self.repair_start_btn.configure(state="normal", text="Run Repair"))
            self.running = False
        except Exception as e:
            self.after(0, lambda: self.repair_status.configure(text=f"Error: {e}", text_color=COLORS["error"]))
            self.after(0, lambda: self.repair_start_btn.configure(state="normal", text="Run Repair"))
            self.running = False

    def _export_diagnostic(self):
        try:
            from tkinter import filedialog
            save_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")],
                initialfile=f"MiMo_Diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )
            if save_path:
                self.diag_export_btn.configure(state="disabled", text="Exporting...")
                threading.Thread(target=self._do_export, args=(save_path,), daemon=True).start()
        except Exception:
            pass

    def _do_export(self, save_path):
        try:
            def log_diag(msg):
                self.after(0, lambda: (
                    self.diag_log_box.configure(state="normal"),
                    self.diag_log_box.insert("end", msg + "\n"),
                    self.diag_log_box.see("end"),
                    self.diag_log_box.configure(state="disabled")
                ))

            self.after(0, lambda: self.diag_status.configure(text="Generating diagnostic report..."))
            log_diag("Collecting system info...")

            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("version.json", json.dumps(VERSION_INFO, indent=2))
                log_diag("Version info collected")

                zf.writestr("manifest.txt",
                    f"MiMo Auto Version: {APP_VERSION}\n"
                    f"Build: {BUILD_NUMBER}\n"
                    f"Build Date: {BUILD_DATE}\n"
                    f"Git Commit: {VERSION_INFO.get('git_commit', 'unknown')}\n"
                    f"Python Version: {sys.version.split()[0]}\n"
                    f"Export Format Version: 3\n"
                    f"Report Generated: {datetime.now().isoformat()}\n")

                zf.writestr("system_info.txt", self._collect_system_info())
                log_diag("System info collected")

                zf.writestr("dependency_versions.txt", self._collect_dep_versions())
                log_diag("Dependency versions collected")

                state = StateManager(self.install_dir)
                zf.writestr("install_state.json", json.dumps(state.state, indent=2))
                log_diag("Install state collected")

                log_dir = get_log_dir(self.install_dir)
                if os.path.exists(log_dir):
                    for f in os.listdir(log_dir):
                        fp = os.path.join(log_dir, f)
                        if os.path.isfile(fp):
                            zf.write(fp, f"logs/{f}")
                    log_diag("Structured logs collected")

            self.after(0, lambda: self.diag_status.configure(
                text=f"Report saved to: {save_path}", text_color=COLORS["success"]))
            log_diag(f"Export complete: {save_path}")
            self.after(0, lambda: self.diag_export_btn.configure(state="normal", text="Export Report"))

            try:
                os.startfile(os.path.dirname(save_path))
            except Exception:
                pass
        except Exception as e:
            self.after(0, lambda: self.diag_status.configure(text=f"Export failed: {e}", text_color=COLORS["error"]))
            self.after(0, lambda: self.diag_export_btn.configure(state="normal", text="Export Report"))

    def _collect_system_info(self):
        lines = []
        try:
            v = sys.getwindowsversion()
            lines.append(f"Windows: {v.major}.{v.minor} Build {v.build}")
        except Exception:
            lines.append("Windows: unknown")
        lines.append(f"Admin: {is_admin()}")
        lines.append(f"Install Dir: {self.install_dir}")
        lines.append(f"Portable: {self.portable_mode}")
        try:
            usage = shutil.disk_usage("C:\\")
            lines.append(f"Disk Free: {usage.free / (1024**3):.1f} GB")
        except Exception:
            pass
        ok, out, _ = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
        lines.append(f"GPU: {out if ok else 'Not detected'}")
        return "\n".join(lines) + "\n"

    def _collect_dep_versions(self):
        lines = []
        for key, dep in DEPENDENCIES.items():
            if dep.get("check_cmd"):
                ok, out, _ = run_cmd(dep["check_cmd"])
                lines.append(f"{dep['name']}: {out if ok else 'NOT FOUND'}")
        ok, out, _ = run_cmd(["mimo", "--version"])
        lines.append(f"MiMo: {out if ok else 'NOT FOUND'}")
        return "\n".join(lines) + "\n"

    def _run_validation(self):
        checks = [
            ("GPU detected", lambda: self.gpu_info["vendor"] == "NVIDIA"),
            ("CUDA available", lambda: self.gpu_info["cuda_available"]),
            ("Model path writable", lambda: self._check_model_path()),
            ("Inference test", lambda: self._check_inference()),
        ]
        for check_name, check_fn in checks:
            try:
                passed = check_fn()
                icon_text = "\u2713" if passed else "\u2717"
                color = COLORS["success"] if passed else COLORS["error"]
            except Exception:
                passed = False
                icon_text = "\u2717"
                color = COLORS["error"]
            item = self.validation_items[check_name]
            self.after(0, lambda i=item, t=icon_text, c=color: (
                i["icon"].configure(text=t, text_color=c),
                i["label"].configure(text_color=COLORS["text_primary"]),
            ))
            time.sleep(0.3)

    def _check_model_path(self):
        try:
            test_dir = os.path.join(os.path.expanduser("~"), "MimoAuto", "models")
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception:
            return False

    def _check_inference(self):
        result = run_inference_smoke_test(0)
        return result.get("passed", False)

    def _finish(self, success=True, msg="Done", error_detail=""):
        self.running = False
        for w in self.complete_btn_frame.winfo_children():
            w.pack_forget()

        if success:
            self.complete_icon_frame.configure(fg_color=COLORS["success_light"])
            self.complete_icon_label.configure(text="\u2713", text_color=COLORS["success"])
            self.complete_title.configure(text=msg, text_color=COLORS["text_primary"])
            self.complete_subtitle.configure(text="MiMo Auto is ready to use", text_color=COLORS["text_secondary"])
            self.complete_error_box.pack_forget()
            self.summary_frame.pack(fill="x", pady=(0, 8))
            self.validation_frame.pack(fill="x", pady=(0, 8))
            self.tips_frame.pack(fill="x", pady=(0, 4))
            self.export_btn.pack(side="right", padx=(0, 6))
            self.launch_btn.pack(side="right")
            self.close_btn.pack(side="right", padx=(0, 8))
        else:
            self.complete_icon_frame.configure(fg_color=COLORS["error_light"])
            self.complete_icon_label.configure(text="\u2717", text_color=COLORS["error"])
            self.complete_title.configure(text=msg, text_color=COLORS["error"])
            self.complete_subtitle.configure(text="Installation could not be completed.", text_color=COLORS["text_secondary"])
            if error_detail:
                self.complete_error_label.configure(text=error_detail)
                self.complete_error_box.pack(fill="x", pady=(0, 4))
            self.validation_frame.pack_forget()
            self.tips_frame.pack_forget()
            self.retry_btn.pack(side="right")
            self.export_btn.pack(side="right", padx=(0, 6))
            self.copy_err_btn.pack(side="right", padx=(0, 6))
            self.open_logs_btn.pack(side="right", padx=(0, 6))
            self.close_btn.pack(side="left")

        self.after(500, lambda: self._show_screen(3))

    def _update_summary(self):
        state_path = os.path.join(self.install_dir, STATE_FILE)
        state = {}
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)
            except Exception:
                pass

        for key in ["nodejs", "git", "mimo"]:
            item = self.summary_items[key]
            dep_data = state.get("deps", {}).get(key, state.get(key, {}))
            if key == "mimo":
                dep_data = state.get("mimo", {})
            if dep_data.get("status") in ("ok", "installed"):
                item["icon"].configure(text="\u2713", text_color=COLORS["success"])
                item["ver"].configure(text=dep_data.get("version", "installed"), text_color=COLORS["text_secondary"])
            else:
                item["icon"].configure(text="\u2717", text_color=COLORS["error"])
                item["ver"].configure(text="not installed", text_color=COLORS["error"])

    def _copy_error(self):
        text = f"MiMo Installer Error Report\n{'='*40}\n"
        text += f"Version: {APP_VERSION}\n"
        text += f"Time: {datetime.now().isoformat()}\n"
        text += f"Install Dir: {self.install_dir}\n"
        text += f"Portable: {self.portable_mode}\n\n"
        text += "Log:\n" + "\n".join(self.engine.log_lines[-20:]) if self.engine else "No log available"
        try:
            subprocess.run(["clip"], input=text.encode("utf-16le"), capture_output=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception:
            pass

    def _open_logs(self):
        log_dir = os.path.join(self.install_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        try:
            os.startfile(log_dir)
        except Exception:
            pass

    def _launch_mimo(self):
        import time as _time
        try:
            mimo_exe = os.path.join(self.install_dir, "mimo.exe")
            if not os.path.exists(mimo_exe):
                mimo_bin = os.path.join(os.path.expanduser("~"), ".mimocode", "bin", "mimo.exe")
                if os.path.exists(mimo_bin):
                    mimo_exe = mimo_bin
                else:
                    ok, out, _ = run_cmd(["where", "mimo"])
                    if ok and out.strip():
                        mimo_exe = out.strip().split("\n")[0].strip()

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

            subprocess.Popen(
                [mimo_exe, "web", "--port", "3000"],
                cwd=os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects"),
                startupinfo=startupinfo,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        except Exception:
            pass


if __name__ == "__main__":
    app = MiMoInstallerApp()
    app.mainloop()
