# 네트워크 IP 설정 변경기 (Network IP Settings Changer)
# Copyright (C) 2025 삶과삶 (Hard-boiled-eggs)
#
# 이 프로그램은 자유 소프트웨어입니다. 당신은 자유 소프트웨어 재단이 공표한
# GNU 일반 공중 사용 허가서 버전 3 또는 그 이후 버전에 따라 이 프로그램을
# 재배포하거나 수정할 수 있습니다.
#
# 이 프로그램은 유용하게 사용될 수 있으리라는 희망에서 배포되지만,
# 특정 목적에 대한 상품성이나 적합성에 대한 묵시적인 보증을 포함한
# 어떠한 형태의 보증도 제공하지 않습니다. 보다 자세한 사항은
# GNU 일반 공중 사용 허가서를 참고하시기 바랍니다.
#
# 당신은 이 프로그램을 통해 GNU 일반 공중 사용 허가서 사본을 받았어야 합니다.
# 그렇지 않은 경우, <https://www.gnu.org/licenses/>를 참고하시기 바랍니다.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


# -*- coding: utf-8 -*-
# Python 2와 3 호환성 및 UTF-8 인코딩 명시

# --- 표준 라이브러리 임포트 ---
import sys
import ctypes
import json
import os
import socket
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import traceback

# --- 제3자 라이브러리 임포트 (오류 처리 포함) ---
try:
    import psutil
except ImportError:
    # 프로그램의 다른 부분이 로드되기 전에 치명적인 오류를 처리
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "오류: 필수 라이브러리 없음",
        "프로그램 실행에 필요한 'psutil' 라이브러리를 찾을 수 없습니다.\n\n"
        "터미널(CMD)에서 아래 명령어를 실행하여 설치해주세요:\n"
        "pip install psutil"
    )
    sys.exit(1)


# --- 전역 상수 ---
APP_VERSION = "1.6"
APP_TITLE = f"네트워크 IP 설정 변경기 v{APP_VERSION}"
PROFILES_FILE = "network_profiles.json"


# --- 핵심 유틸리티 함수 ---
def is_admin():
    """
    현재 스크립트가 관리자 권한으로 실행 중인지 확인합니다.
    ctypes를 통해 Windows의 기본 API인 Shell32.dll의 IsUserAnAdmin 함수를 호출합니다.
    이 방식은 모든 현대 윈도우 버전에서 안정적으로 작동합니다.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """
    스크립트를 관리자 권한으로 다시 실행합니다.
    ShellExecuteW API를 사용하여 권한 상승(UAC) 프롬프트를 띄웁니다.
    """
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)


# --- 메인 애플리케이션 클래스 ---
class NetworkChangerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("520x540")
        self.root.resizable(False, False)

        self.profiles = {}
        
        self.create_widgets()
        self.adapter_combo.bind("<<ComboboxSelected>>", self.on_adapter_selected)
        
        self.load_profiles()
        self.populate_adapters()

    def create_widgets(self):
        # UI 요소 생성 (이전과 동일)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        adapter_frame = ttk.LabelFrame(main_frame, text="1. 네트워크 어댑터 선택", padding="10")
        adapter_frame.pack(fill=tk.X, pady=5)
        adapter_selection_frame = ttk.Frame(adapter_frame)
        adapter_selection_frame.pack(fill=tk.X)
        ttk.Label(adapter_selection_frame, text="이더넷 어댑터:").pack(side=tk.LEFT, padx=(0, 10))
        self.adapter_var = tk.StringVar()
        self.adapter_combo = ttk.Combobox(adapter_selection_frame, textvariable=self.adapter_var, state="readonly", width=40)
        self.adapter_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        current_ip_frame = ttk.Frame(adapter_frame)
        current_ip_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(current_ip_frame, text="현재 IP 주소:").pack(side=tk.LEFT)
        self.current_ip_var = tk.StringVar(value="-")
        ttk.Label(current_ip_frame, textvariable=self.current_ip_var, font=("Segoe UI", 10, "bold"), foreground="#2E8B57").pack(side=tk.LEFT, padx=4)
        mode_frame = ttk.LabelFrame(main_frame, text="2. IP 주소 설정", padding="10")
        mode_frame.pack(fill=tk.X, pady=5)
        self.dhcp_button = ttk.Button(mode_frame, text="DHCP로 설정 (자동 주소 받기)", command=self.set_dhcp)
        self.dhcp_button.pack(fill=tk.X, pady=5)
        static_frame = ttk.Frame(mode_frame, padding="5")
        static_frame.pack(fill=tk.X, pady=5)
        ttk.Label(static_frame, text="IP 주소:", width=15).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.ip_entry = ttk.Entry(static_frame, width=35)
        self.ip_entry.grid(row=0, column=1, sticky=tk.W)
        ttk.Label(static_frame, text="서브넷 마스크:", width=15).grid(row=1, column=0, sticky=tk.W, pady=2)
        self.subnet_entry = ttk.Entry(static_frame, width=35)
        self.subnet_entry.grid(row=1, column=1, sticky=tk.W)
        self.subnet_entry.insert(0, "255.255.255.0")
        ttk.Label(static_frame, text="기본 게이트웨이:", width=15).grid(row=2, column=0, sticky=tk.W, pady=2)
        self.gateway_entry = ttk.Entry(static_frame, width=35)
        self.gateway_entry.grid(row=2, column=1, sticky=tk.W)
        self.static_button = ttk.Button(static_frame, text="수동 IP로 적용", command=self.set_static)
        self.static_button.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.E)
        profile_frame = ttk.LabelFrame(main_frame, text="3. 프로필 관리", padding="10")
        profile_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.profile_list = tk.Listbox(profile_frame, height=6)
        self.profile_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        profile_btn_frame = ttk.Frame(profile_frame)
        profile_btn_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.load_btn = ttk.Button(profile_btn_frame, text="불러오기", command=self.load_selected_profile)
        self.load_btn.pack(fill=tk.X, pady=2, ipady=2)
        self.save_btn = ttk.Button(profile_btn_frame, text="저장하기", command=self.save_current_profile)
        self.save_btn.pack(fill=tk.X, pady=2, ipady=2)
        self.edit_btn = ttk.Button(profile_btn_frame, text="이름 수정", command=self.edit_selected_profile)
        self.edit_btn.pack(fill=tk.X, pady=2, ipady=2)
        self.delete_btn = ttk.Button(profile_btn_frame, text="삭제하기", command=self.delete_selected_profile)
        self.delete_btn.pack(fill=tk.X, pady=2, ipady=2)

    def on_adapter_selected(self, event=None):
        """
        psutil을 사용하여 어댑터의 현재 IP를 조회합니다.
        psutil은 OS 버전에 따른 복잡성을 추상화하여 유지보수를 용이하게 합니다.
        """
        adapter_name = self.adapter_var.get()
        if not adapter_name:
            self.current_ip_var.set("-")
            return
        current_ip = "N/A"
        try:
            addrs = psutil.net_if_addrs().get(adapter_name, [])
            for addr in addrs:
                if hasattr(addr, 'family') and addr.family == socket.AF_INET:
                    current_ip = addr.address
                    break
        except Exception:
            current_ip = "오류 발생"
            traceback.print_exc()
        self.current_ip_var.set(current_ip)

    def run_command(self, command):
        """
        Windows의 표준 도구(netsh)를 실행하여 하위 호환성을 극대화합니다.
        향후 명령어가 변경될 경우, 이 함수를 호출하는 부분의 명령어 문자열만 수정하면 됩니다.
        """
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(command, check=True, capture_output=True, text=True, shell=True, startupinfo=startupinfo)
            return True
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.strip() if e.stderr else e.stdout.strip()
            messagebox.showerror("명령 실행 오류", f"오류가 발생했습니다:\n{error_message}")
            return False
        except Exception as e:
            messagebox.showerror("알 수 없는 오류", f"명령 실행 중 알 수 없는 오류 발생: {e}")
            return False

    def set_dhcp(self):
        adapter_name = self.adapter_var.get()
        if not adapter_name:
            messagebox.showwarning("경고", "먼저 네트워크 어댑터를 선택하세요.")
            return
        if messagebox.askyesno("확인", f"'{adapter_name}'을(를) DHCP로 설정하시겠습니까?"):
            command = f'netsh interface ipv4 set address name="{adapter_name}" source=dhcp'
            if self.run_command(command):
                dns_command = f'netsh interface ipv4 set dnsservers name="{adapter_name}" source=dhcp'
                self.run_command(dns_command)
                messagebox.showinfo("성공", f"'{adapter_name}'이(가) DHCP로 성공적으로 설정되었습니다.")
                self.on_adapter_selected()

    def set_static(self):
        adapter_name = self.adapter_var.get()
        ip, subnet, gateway = self.ip_entry.get(), self.subnet_entry.get(), self.gateway_entry.get()
        if not adapter_name:
            messagebox.showwarning("경고", "먼저 네트워크 어댑터를 선택하세요.")
            return
        if not all([ip, subnet, gateway]):
            messagebox.showwarning("경고", "IP 주소, 서브넷 마스크, 기본 게이트웨이를 모두 입력하세요.")
            return
        if messagebox.askyesno("확인", f"'{adapter_name}'에 다음 고정 IP를 설정하시겠습니까?\n\nIP: {ip}\n서브넷: {subnet}\n게이트웨이: {gateway}"):
            command = f'netsh interface ipv4 set address name="{adapter_name}" static {ip} {subnet} {gateway}'
            if self.run_command(command):
                messagebox.showinfo("성공", "고정 IP가 성공적으로 설정되었습니다.")
                self.on_adapter_selected()

    # 이하 다른 모든 함수는 UI 로직이므로 OS 호환성과 무관하여 이전과 동일합니다.
    def populate_adapters(self):
        adapters = []
        try:
            stats = psutil.net_if_stats(); addrs = psutil.net_if_addrs()
            for name, snic_stats in stats.items():
                if ('ethernet' in name.lower() or '이더넷' in name.lower()) and snic_stats.isup:
                    if not any("virtual" in addr.address.lower() or "vmware" in addr.address.lower() for addr in addrs.get(name, [])):
                        adapters.append(name)
        except Exception as e: messagebox.showerror("오류", f"네트워크 어댑터를 찾는 중 오류 발생: {e}")
        if adapters:
            self.adapter_combo['values'] = adapters; self.adapter_combo.current(0); self.on_adapter_selected()
        else: messagebox.showwarning("경고", "활성화된 유선 이더넷 어댑터를 찾을 수 없습니다."); self.current_ip_var.set("어댑터 없음")
    def edit_selected_profile(self):
        selection_indices = self.profile_list.curselection()
        if not selection_indices: messagebox.showwarning("경고", "수정할 프로필을 목록에서 선택하세요.", parent=self.root); return
        original_name = self.profile_list.get(selection_indices[0])
        new_name = simpledialog.askstring("프로필 이름 수정", f"'{original_name}'의 새 이름을 입력하세요:", initialvalue=original_name, parent=self.root)
        if not new_name or not new_name.strip(): return
        new_name = new_name.strip()
        if new_name == original_name: return
        if new_name in self.profiles: messagebox.showerror("오류", "이미 사용 중인 이름입니다.", parent=self.root); return
        self.profiles[new_name] = self.profiles.pop(original_name); self.save_profiles(); self.update_profile_listbox()
        try:
            new_index = list(sorted(self.profiles.keys())).index(new_name)
            self.profile_list.selection_set(new_index); self.profile_list.see(new_index)
        except ValueError: pass
    def load_profiles(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f: self.profiles = json.load(f)
            except json.JSONDecodeError: self.profiles = {}
        self.update_profile_listbox()
    def save_profiles(self):
        with open(PROFILES_FILE, 'w') as f: json.dump(self.profiles, f, indent=4)
    def update_profile_listbox(self):
        self.profile_list.delete(0, tk.END); [self.profile_list.insert(tk.END, name) for name in sorted(self.profiles.keys())]
    def load_selected_profile(self):
        selection = self.profile_list.curselection()
        if not selection: messagebox.showwarning("경고", "불러올 프로필을 목록에서 선택하세요."); return
        profile_name = self.profile_list.get(selection[0]); profile_data = self.profiles.get(profile_name)
        if profile_data:
            self.ip_entry.delete(0, tk.END); self.ip_entry.insert(0, profile_data.get("ip", ""))
            self.subnet_entry.delete(0, tk.END); self.subnet_entry.insert(0, profile_data.get("subnet", "255.255.255.0"))
            self.gateway_entry.delete(0, tk.END); self.gateway_entry.insert(0, profile_data.get("gateway", ""))
            messagebox.showinfo("완료", f"'{profile_name}' 프로필을 불러왔습니다.")
    def save_current_profile(self):
        ip, subnet, gateway = self.ip_entry.get(), self.subnet_entry.get(), self.gateway_entry.get()
        if not ip or not gateway: messagebox.showwarning("경고", "저장할 IP 주소와 게이트웨이 정보를 입력하세요."); return
        profile_name = simpledialog.askstring("프로필 저장", "저장할 프로필 이름을 입력하세요:", parent=self.root)
        if profile_name and profile_name.strip():
            profile_name = profile_name.strip()
            if profile_name in self.profiles and not messagebox.askyesno("경고", "같은 이름의 프로필이 이미 존재합니다. 덮어쓰시겠습니까?"): return
            self.profiles[profile_name] = {"ip": ip, "subnet": subnet, "gateway": gateway}; self.save_profiles(); self.update_profile_listbox(); messagebox.showinfo("성공", f"'{profile_name}' 프로필이 저장되었습니다.")
    def delete_selected_profile(self):
        selection = self.profile_list.curselection()
        if not selection: messagebox.showwarning("경고", "삭제할 프로필을 목록에서 선택하세요."); return
        profile_name = self.profile_list.get(selection[0])
        if messagebox.askyesno("확인", f"'{profile_name}' 프로필을 정말 삭제하시겠습니까?"):
            if profile_name in self.profiles:
                del self.profiles[profile_name]; self.save_profiles(); self.update_profile_listbox(); messagebox.showinfo("성공", f"'{profile_name}' 프로필이 삭제되었습니다.")


# --- 프로그램 실행 진입점 ---
if __name__ == "__main__":
    # 1. 관리자 권한 확인 및 요청
    if not is_admin():
        run_as_admin()
        sys.exit() # 권한 상승 후 재실행되므로 현재 프로세스는 종료

    # 2. 메인 애플리케이션 실행 (오류 발생 시 메시지 박스로 표시)
    try:
        root = tk.Tk()
        app = NetworkChangerApp(root)
        root.mainloop()
    except Exception as e:
        # 최종 예외 처리: 예상치 못한 모든 오류를 잡아 사용자에게 보여줌
        error_info = traceback.format_exc()
        messagebox.showerror("치명적인 오류 발생", f"프로그램 실행 중 예측하지 못한 오류가 발생했습니다:\n\n{error_info}")
        sys.exit(1)