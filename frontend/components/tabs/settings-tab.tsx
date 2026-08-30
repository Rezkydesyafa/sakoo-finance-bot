"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  apiClient,
  ApiError,
  type NotificationPreferencesResponse,
  type NotificationPreferencesUpdate,
} from "@/lib/api";
import { clearAuthToken, getStoredAuthToken } from "@/lib/auth-storage";

type SettingsTabProps = {
  userName: string;
  userEmail: string;
  userPhone: string;
  onClose?: () => void;
};

export function SettingsTab({ userName, userEmail, userPhone, onClose }: SettingsTabProps) {
  const router = useRouter();
  const [profileImage, setProfileImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const savedImage = localStorage.getItem("sakoo_profile_image");
    if (savedImage) {
      setProfileImage(savedImage);
    }
  }, []);
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [notificationPreferences, setNotificationPreferences] = useState<NotificationPreferencesResponse>({
    daily_reminder_enabled: false,
    daily_reminder_time: "20:00",
    weekly_summary_enabled: false,
    monthly_summary_enabled: false,
    budget_alert_enabled: true,
    timezone: "Asia/Jakarta",
    active_channels: [],
  });
  const [notificationLoading, setNotificationLoading] = useState(true);
  const [notificationSaving, setNotificationSaving] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState("");
  const [notificationError, setNotificationError] = useState("");

  useEffect(() => {
    const token = getStoredAuthToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    apiClient.notifications.preferences(token)
      .then(setNotificationPreferences)
      .catch((error) => handleNotificationAuthError(error, router, setNotificationError))
      .finally(() => setNotificationLoading(false));
  }, [router]);

  const [modalOpen, setModalOpen] = useState<"none" | "logout" | "deactivate" | "delete">("none");

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError("Perubahan password belum tersedia.");
  };

  const handleConfirmAction = () => {
    if (modalOpen === "logout") {
      clearAuthToken();
      router.replace("/login");
      router.refresh();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setProfileImage(reader.result as string);
      };
      reader.readAsDataURL(e.target.files[0]);
    }
  };

  const handleSaveProfile = () => {
    if (profileImage) {
      localStorage.setItem("sakoo_profile_image", profileImage);
      window.dispatchEvent(new Event("profile_image_updated"));
    }
    alert("Foto profil disimpan di perangkat ini.");
  };

  const handleSaveNotifications = async () => {
    const token = getStoredAuthToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setNotificationSaving(true);
    setNotificationMessage("");
    setNotificationError("");
    const payload: NotificationPreferencesUpdate = {
      daily_reminder_enabled: notificationPreferences.daily_reminder_enabled,
      daily_reminder_time: notificationPreferences.daily_reminder_time,
      weekly_summary_enabled: notificationPreferences.weekly_summary_enabled,
      monthly_summary_enabled: notificationPreferences.monthly_summary_enabled,
      budget_alert_enabled: notificationPreferences.budget_alert_enabled,
      timezone: notificationPreferences.timezone,
    };
    try {
      setNotificationPreferences(await apiClient.notifications.updatePreferences(token, payload));
      setNotificationMessage("Pengaturan notifikasi berhasil disimpan.");
    } catch (error) {
      handleNotificationAuthError(error, router, setNotificationError);
    } finally {
      setNotificationSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      <div className="flex items-center gap-4 mb-2">
        <button 
          onClick={() => {
            if (onClose) {
              onClose();
            } else {
              router.push("/?tab=overview");
            }
          }} 
          className="w-10 h-10 flex items-center justify-center rounded-full bg-white shadow-sm hover:bg-[#F1F2F0] transition-colors text-[#1a1c1b] border border-[#E8E8E8] cursor-pointer"
        >
          <span className="material-symbols-outlined text-[20px]">arrow_back</span>
        </button>
        <h2 className="text-2xl font-semibold text-[#1a1c1b]">Profil</h2>
      </div>

      {/* Profile Header */}
      <div className="bg-white rounded-[28px] p-6 sm:p-8 card-shadow flex flex-col sm:flex-row items-center sm:items-start gap-6">
        <div className="relative group">
          <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-full bg-gradient-to-tr from-[#c7ff00] to-[#5FCF6A] p-1">
            <div className="w-full h-full bg-white rounded-full flex items-center justify-center overflow-hidden border-2 border-white">
              {profileImage ? (
                <img src={profileImage} alt="Profile" className="w-full h-full object-cover" />
              ) : (
                <span className="material-symbols-outlined text-6xl text-[#6F6F6F]">person</span>
              )}
            </div>
          </div>
                  <input
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            className="hidden" 
            accept="image/*" 
          />
          <button onClick={() => fileInputRef.current?.click()} className="absolute bottom-0 right-0 bg-[#1a1c1b] text-white p-2 rounded-full border-2 border-white hover:scale-105 transition-transform cursor-pointer">
            <span className="material-symbols-outlined text-[16px]">photo_camera</span>
          </button>
        </div>
        <div className="flex-1 text-center sm:text-left flex flex-col justify-center h-full pt-2">
          <h3 className="text-xl sm:text-2xl font-semibold text-[#1a1c1b] mb-1">{userName}</h3>
          <p className="text-sm text-[#6F6F6F] mb-4">{userEmail}</p>
          <div className="flex justify-center sm:justify-start gap-3">
            <button className="bg-[#F1F2F0] hover:bg-[#E8E8E8] text-[#1a1c1b] px-5 py-2 rounded-full text-xs font-semibold transition-colors border-none cursor-pointer flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">edit</span>
              Edit Profil
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Navigation/Sections List */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-[24px] p-2 card-shadow flex flex-col">
            <div className="p-3 text-xs font-semibold text-[#6F6F6F] uppercase tracking-wider">Navigasi Pengaturan</div>
            <a href="#info" className="flex items-center gap-3 p-3 rounded-xl hover:bg-[#F1F2F0] transition-colors text-[#1a1c1b] font-semibold text-sm">
              <span className="material-symbols-outlined text-[#6F6F6F]">manage_accounts</span>
              Informasi Akun
            </a>
            <a href="#security" className="flex items-center gap-3 p-3 rounded-xl hover:bg-[#F1F2F0] transition-colors text-[#1a1c1b] font-semibold text-sm">
              <span className="material-symbols-outlined text-[#6F6F6F]">security</span>
              Keamanan Akun
            </a>
            <a href="#preferences" className="flex items-center gap-3 p-3 rounded-xl hover:bg-[#F1F2F0] transition-colors text-[#1a1c1b] font-semibold text-sm">
              <span className="material-symbols-outlined text-[#6F6F6F]">tune</span>
              Preferensi Aplikasi
            </a>
            <a href="#privacy" className="flex items-center gap-3 p-3 rounded-xl hover:bg-[#F1F2F0] transition-colors text-[#1a1c1b] font-semibold text-sm">
              <span className="material-symbols-outlined text-[#6F6F6F]">shield_lock</span>
              Privasi
            </a>
            <a href="#help" className="flex items-center gap-3 p-3 rounded-xl hover:bg-[#F1F2F0] transition-colors text-[#1a1c1b] font-semibold text-sm">
              <span className="material-symbols-outlined text-[#6F6F6F]">help</span>
              Bantuan
            </a>
            <a href="#actions" className="flex items-center gap-3 p-3 rounded-xl hover:bg-red-50 transition-colors text-red-500 font-semibold text-sm mt-2 border-t border-[#E8E8E8]">
              <span className="material-symbols-outlined">warning</span>
              Aksi Akun
            </a>
          </div>
        </div>

        {/* Right Column: Settings Content */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Informasi Akun */}
          <section id="info" className="bg-white rounded-[28px] p-6 sm:p-8 card-shadow scroll-mt-24">
            <h3 className="text-lg font-semibold text-[#1a1c1b] mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-[#4e6700]">manage_accounts</span>
              Informasi Akun
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Nama Lengkap</label>
                  <input type="text" defaultValue={userName} disabled className="w-full bg-[#F1F2F0] opacity-70 border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] cursor-not-allowed" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Nomor Telepon</label>
                  <input type="tel" defaultValue={userPhone} disabled className="w-full bg-[#F1F2F0] opacity-70 border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] cursor-not-allowed" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Email Utama</label>
                <div className="relative">
                  <input type="email" defaultValue={userEmail} disabled className="w-full bg-[#F1F2F0] opacity-70 border-none rounded-xl py-3 px-4 text-sm font-medium text-[#1a1c1b] cursor-not-allowed" />
                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-semibold text-[#5FCF6A]">Terverifikasi</span>
                </div>
              </div>
              <button onClick={handleSaveProfile} className="bg-[#4e6700] hover:bg-[#3a4d00] text-white px-6 py-2.5 rounded-full text-xs font-semibold transition-colors border-none cursor-pointer mt-2">
                Simpan Foto di Perangkat
              </button>
            </div>
          </section>

          {/* Keamanan Akun */}
          <section id="security" className="bg-white rounded-[28px] p-6 sm:p-8 card-shadow scroll-mt-24">
            <h3 className="text-lg font-semibold text-[#1a1c1b] mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-[#4e6700]">security</span>
              Keamanan Akun
            </h3>
            
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div className="p-4 rounded-2xl bg-orange-50 border border-orange-100 mb-6 flex items-start gap-3">
                <span className="material-symbols-outlined text-orange-500 text-xl">info</span>
                <p className="text-xs text-orange-800 font-medium leading-relaxed">
                  Gunakan minimal 8 karakter dengan kombinasi huruf dan angka untuk membuat password yang kuat.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Password Lama</label>
                <div className="relative">
                   <input
                     type={showOldPassword ? "text" : "password"}
                     value={oldPassword}
                     onChange={(e) => setOldPassword(e.target.value)}
                     disabled
                     className="w-full bg-[#F1F2F0] opacity-70 border-none rounded-xl py-3 pl-4 pr-12 text-sm font-medium text-[#1a1c1b] cursor-not-allowed"
                  />
                  <button type="button" disabled onClick={() => setShowOldPassword(!showOldPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6F6F6F] cursor-not-allowed">
                    <span className="material-symbols-outlined text-[20px]">{showOldPassword ? 'visibility' : 'visibility_off'}</span>
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Password Baru</label>
                  <div className="relative">
                    <input 
                      type={showNewPassword ? "text" : "password"}
                     value={newPassword}
                     onChange={(e) => setNewPassword(e.target.value)}
                     disabled
                     className="w-full bg-[#F1F2F0] opacity-70 border-none rounded-xl py-3 pl-4 pr-12 text-sm font-medium text-[#1a1c1b] cursor-not-allowed"
                    />
                    <button type="button" disabled onClick={() => setShowNewPassword(!showNewPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6F6F6F] cursor-not-allowed">
                      <span className="material-symbols-outlined text-[20px]">{showNewPassword ? 'visibility' : 'visibility_off'}</span>
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#6F6F6F] mb-1.5">Konfirmasi Password Baru</label>
                  <div className="relative">
                    <input 
                      type={showConfirmPassword ? "text" : "password"}
                     value={confirmPassword}
                     onChange={(e) => setConfirmPassword(e.target.value)}
                     disabled
                     className="w-full bg-[#F1F2F0] opacity-70 border-none rounded-xl py-3 pl-4 pr-12 text-sm font-medium text-[#1a1c1b] cursor-not-allowed"
                    />
                    <button type="button" disabled onClick={() => setShowConfirmPassword(!showConfirmPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6F6F6F] cursor-not-allowed">
                      <span className="material-symbols-outlined text-[20px]">{showConfirmPassword ? 'visibility' : 'visibility_off'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {passwordError && (
                <p className="text-red-500 text-xs font-semibold">{passwordError}</p>
              )}

              <button type="submit" disabled className="bg-[#4e6700] opacity-50 text-white px-6 py-2.5 rounded-full text-xs font-semibold border-none cursor-not-allowed mt-2">
                Belum Tersedia
              </button>
            </form>
          </section>

          {/* Preferensi Aplikasi */}
          <section id="preferences" className="bg-white rounded-[28px] p-6 sm:p-8 card-shadow scroll-mt-24">
            <h3 className="text-lg font-semibold text-[#1a1c1b] mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-[#4e6700]">tune</span>
              Preferensi Aplikasi
            </h3>
            <div className="space-y-6">
              {notificationLoading ? (
                <p className="text-sm text-[#6F6F6F]">Memuat pengaturan notifikasi...</p>
              ) : (
                <>
                  <div className="rounded-2xl bg-[#F8F9F6] p-4">
                    <div className="text-xs font-semibold text-[#6F6F6F] uppercase tracking-wider mb-2">Dikirim melalui</div>
                    {notificationPreferences.active_channels.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {notificationPreferences.active_channels.map((channel) => (
                          <span key={channel} className="rounded-full bg-[#E9F8D0] px-3 py-1 text-xs font-semibold text-[#4e6700] capitalize">
                            {channel}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs font-medium text-orange-700">Belum ada WhatsApp atau Telegram aktif. Hubungkan bot agar notifikasi dapat dikirim.</p>
                    )}
                  </div>

                  <NotificationToggle
                    title="Pengingat dan rekap harian"
                    description="Ingatkan pencatatan atau kirim rekap singkat jika transaksi sudah ada."
                    checked={notificationPreferences.daily_reminder_enabled}
                    onChange={(checked) => setNotificationPreferences((value) => ({ ...value, daily_reminder_enabled: checked }))}
                  />

                  <div className="border-t border-[#E8E8E8] pt-6 flex items-center justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold text-[#1a1c1b] mb-1">Jam pengingat harian</div>
                      <div className="text-xs text-[#6F6F6F]">Mengikuti zona waktu yang dipilih.</div>
                    </div>
                    <input
                      type="time"
                      value={notificationPreferences.daily_reminder_time}
                      disabled={!notificationPreferences.daily_reminder_enabled}
                      onChange={(event) => setNotificationPreferences((value) => ({ ...value, daily_reminder_time: event.target.value }))}
                      className="bg-[#F1F2F0] disabled:opacity-50 border-none rounded-xl py-2 px-4 text-xs font-semibold text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00]"
                    />
                  </div>

                  <NotificationToggle
                    title="Ringkasan mingguan"
                    description="Dikirim setiap Senin pukul 08.00 untuk minggu sebelumnya."
                    checked={notificationPreferences.weekly_summary_enabled}
                    onChange={(checked) => setNotificationPreferences((value) => ({ ...value, weekly_summary_enabled: checked }))}
                  />
                  <NotificationToggle
                    title="Ringkasan bulanan"
                    description="Dikirim tanggal 1 pukul 08.00 untuk bulan sebelumnya."
                    checked={notificationPreferences.monthly_summary_enabled}
                    onChange={(checked) => setNotificationPreferences((value) => ({ ...value, monthly_summary_enabled: checked }))}
                  />
                  <NotificationToggle
                    title="Peringatan budget"
                    description="Kabar saat pemakaian budget mencapai 80% dan 100%."
                    checked={notificationPreferences.budget_alert_enabled}
                    onChange={(checked) => setNotificationPreferences((value) => ({ ...value, budget_alert_enabled: checked }))}
                  />

                  <div className="border-t border-[#E8E8E8] pt-6 flex items-center justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold text-[#1a1c1b] mb-1">Zona waktu</div>
                      <div className="text-xs text-[#6F6F6F]">Dipakai untuk semua jadwal notifikasi.</div>
                    </div>
                    <select
                      value={notificationPreferences.timezone}
                      onChange={(event) => setNotificationPreferences((value) => ({
                        ...value,
                        timezone: event.target.value as NotificationPreferencesResponse["timezone"],
                      }))}
                      className="bg-[#F1F2F0] border-none rounded-xl py-2 px-4 text-xs font-semibold text-[#1a1c1b] focus:ring-1 focus:ring-[#c7ff00] cursor-pointer"
                    >
                      <option value="Asia/Jakarta">WIB</option>
                      <option value="Asia/Makassar">WITA</option>
                      <option value="Asia/Jayapura">WIT</option>
                    </select>
                  </div>

                  {notificationError && <p className="text-xs font-semibold text-red-600">{notificationError}</p>}
                  {notificationMessage && <p className="text-xs font-semibold text-green-700">{notificationMessage}</p>}
                  <button
                    type="button"
                    disabled={notificationSaving}
                    onClick={handleSaveNotifications}
                    className="bg-[#4e6700] disabled:opacity-60 hover:bg-[#3a4d00] text-white px-6 py-2.5 rounded-full text-xs font-semibold transition-colors border-none cursor-pointer"
                  >
                    {notificationSaving ? "Menyimpan..." : "Simpan Pengaturan"}
                  </button>
                </>
              )}
              <div className="flex items-center justify-between border-t border-[#E8E8E8] pt-6">
                <div>
                  <div className="text-sm font-semibold text-[#1a1c1b] mb-1">Mode Gelap (Dark Mode)</div>
                  <div className="text-xs text-[#6F6F6F]">Ganti tema aplikasi menjadi gelap.</div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" disabled className="sr-only peer" />
                  <div className="w-11 h-6 bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#5FCF6A]"></div>
                </label>
              </div>
              <div className="flex items-center justify-between border-t border-[#E8E8E8] pt-6">
                <div>
                  <div className="text-sm font-semibold text-[#1a1c1b] mb-1">Mata Uang Default</div>
                  <div className="text-xs text-[#6F6F6F]">Pilih mata uang yang digunakan untuk laporan.</div>
                </div>
                <select disabled className="bg-[#F1F2F0] opacity-70 border-none rounded-xl py-2 px-4 text-xs font-semibold text-[#1a1c1b] cursor-not-allowed">
                  <option>IDR (Rupiah)</option>
                  <option>USD (Dollar)</option>
                </select>
              </div>
            </div>
          </section>

          {/* Privasi & Bantuan */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <section id="privacy" className="bg-white rounded-[28px] p-6 card-shadow scroll-mt-24">
              <h3 className="text-lg font-semibold text-[#1a1c1b] mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-[#4e6700]">shield_lock</span>
                Privasi
              </h3>
              <p className="text-xs text-[#6F6F6F] leading-relaxed mb-4">
                Data keuangan Anda dienkripsi secara aman. Kami tidak menjual data Anda kepada pihak ketiga.
              </p>
              <span className="text-xs font-semibold text-[#6F6F6F]">Dokumen privasi belum dipublikasikan.</span>
            </section>

            <section id="help" className="bg-white rounded-[28px] p-6 card-shadow scroll-mt-24">
              <h3 className="text-lg font-semibold text-[#1a1c1b] mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-[#4e6700]">help</span>
                Bantuan
              </h3>
              <p className="text-xs text-[#6F6F6F] leading-relaxed mb-4">
                Ada kendala atau pertanyaan? Tim support kami siap membantu Anda 24/7.
              </p>
              <span className="text-xs font-semibold text-[#6F6F6F]">Kanal support belum tersedia.</span>
            </section>
          </div>

          {/* Aksi Akun (Danger Zone) */}
          <section id="actions" className="bg-red-50 rounded-[28px] p-6 sm:p-8 border border-red-100 scroll-mt-24">
            <h3 className="text-lg font-semibold text-red-600 mb-2 flex items-center gap-2">
              <span className="material-symbols-outlined">warning</span>
              Aksi Akun (Danger Zone)
            </h3>
            <p className="text-xs text-red-800/80 mb-6 font-medium">
              Tindakan di area ini dapat mengubah atau menghapus data Anda. Harap berhati-hati.
            </p>

            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-white/60">
                <div>
                  <div className="text-sm font-semibold text-[#1a1c1b]">Keluar (Sign Out)</div>
                  <div className="text-xs text-[#6F6F6F]">Keluar dari sesi ini pada perangkat Anda.</div>
                </div>
                <button onClick={() => setModalOpen("logout")} className="bg-white border border-[#E8E8E8] hover:bg-neutral-50 text-[#1a1c1b] px-5 py-2 rounded-full text-xs font-semibold transition-colors cursor-pointer whitespace-nowrap">
                  Sign Out
                </button>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-white/60">
                <div>
                  <div className="text-sm font-semibold text-[#1a1c1b]">Nonaktifkan Akun</div>
                  <div className="text-xs text-[#6F6F6F]">Sembunyikan akun Anda untuk sementara waktu.</div>
                </div>
                <button disabled className="bg-white opacity-60 border border-orange-200 text-orange-600 px-5 py-2 rounded-full text-xs font-semibold cursor-not-allowed whitespace-nowrap">
                  Belum Tersedia
                </button>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-white/60">
                <div>
                  <div className="text-sm font-semibold text-red-600">Hapus Akun Permanen</div>
                  <div className="text-xs text-[#6F6F6F]">Hapus seluruh data transaksi dan akun selamanya.</div>
                </div>
                <button disabled className="bg-red-600 opacity-60 text-white px-5 py-2 rounded-full text-xs font-semibold border-none cursor-not-allowed whitespace-nowrap">
                  Belum Tersedia
                </button>
              </div>
            </div>
          </section>

        </div>
      </div>

      {/* MODAL / NOTIFICATION FOR CRITICAL ACTIONS */}
      {modalOpen !== "none" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl p-8 w-full max-w-sm shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4 mx-auto 
              ${modalOpen === 'delete' ? 'bg-red-100 text-red-600' : modalOpen === 'deactivate' ? 'bg-orange-100 text-orange-600' : 'bg-neutral-100 text-[#1a1c1b]'}">
              <span className="material-symbols-outlined text-2xl">
                {modalOpen === "delete" ? "delete_forever" : modalOpen === "deactivate" ? "pause_circle" : "logout"}
              </span>
            </div>
            
            <h3 className="text-lg font-semibold text-center text-[#1a1c1b] mb-2">
              {modalOpen === "delete" ? "Hapus Akun Permanen?" : modalOpen === "deactivate" ? "Nonaktifkan Akun?" : "Keluar dari Akun?"}
            </h3>
            <p className="text-sm text-center text-[#6F6F6F] mb-8">
              {modalOpen === "delete" 
                ? "Tindakan ini tidak dapat dibatalkan. Semua data riwayat transaksi dan informasi Anda akan dihapus selamanya." 
                : modalOpen === "deactivate" 
                ? "Akun Anda akan dinonaktifkan sementara dan Anda tidak akan menerima pemberitahuan apa pun. Anda dapat mengaktifkannya lagi dengan masuk kembali."
                : "Anda harus login kembali untuk mengakses data Anda. Lanjutkan?"}
            </p>
            
            <div className="flex flex-col gap-3">
              <button onClick={handleConfirmAction} className={`w-full py-3 rounded-full text-sm font-semibold border-none cursor-pointer transition-colors ${
                modalOpen === "delete" ? "bg-red-600 hover:bg-red-700 text-white" : 
                modalOpen === "deactivate" ? "bg-orange-500 hover:bg-orange-600 text-white" : 
                "bg-[#1a1c1b] hover:bg-black text-white"
              }`}>
                Ya, {modalOpen === "delete" ? "Hapus" : modalOpen === "deactivate" ? "Nonaktifkan" : "Sign Out"}
              </button>
              <button onClick={() => setModalOpen("none")} className="w-full py-3 bg-white border border-[#E8E8E8] text-[#1a1c1b] rounded-full text-sm font-semibold hover:bg-[#F1F2F0] transition-colors cursor-pointer">
                Batal
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

function NotificationToggle({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-[#E8E8E8] pt-6 first:border-0 first:pt-0">
      <div>
        <div className="text-sm font-semibold text-[#1a1c1b] mb-1">{title}</div>
        <div className="text-xs text-[#6F6F6F]">{description}</div>
      </div>
      <label className="relative inline-flex items-center cursor-pointer shrink-0">
        <input type="checkbox" className="sr-only peer" checked={checked} onChange={(event) => onChange(event.target.checked)} />
        <div className="w-11 h-6 bg-[#E8E8E8] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#5FCF6A]"></div>
      </label>
    </div>
  );
}

function handleNotificationAuthError(
  error: unknown,
  router: ReturnType<typeof useRouter>,
  setError: (message: string) => void,
) {
  if (error instanceof ApiError && error.status === 401) {
    clearAuthToken();
    router.replace("/login");
    return;
  }
  setError("Pengaturan notifikasi belum dapat dimuat atau disimpan. Coba lagi.");
}
