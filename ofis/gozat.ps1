# KONSOL -- klasor secme penceresi (ofis/konsol.py -> gozat()).
# Gezgin'in MODERN secicisi (IFileOpenDialog + FOS_PICKFOLDERS): sol
# kenarda Masaustu/Belgeler, adres cubugu, yeni klasor. Secilen yolu
# stdout'a yazar; vazgecilirse bos. OFIS_GOZAT_DENE=1: yalniz derler
# (sinama pencere ACMAZ).
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class OfisKlasorSec {
  [ComImport, Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")] class FileOpenDialogRCW {}
  [ComImport, Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IShellItem {
    void BindToHandler(IntPtr pbc, ref Guid bhid, ref Guid riid, out IntPtr ppv);
    void GetParent(out IShellItem ppsi);
    void GetDisplayName(uint sigdn, [MarshalAs(UnmanagedType.LPWStr)] out string name);
  }
  [ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IFileOpenDialog {
    [PreserveSig] int Show(IntPtr hwnd);
    void SetFileTypes(uint c, IntPtr f);
    void SetFileTypeIndex(uint i);
    void GetFileTypeIndex(out uint i);
    void Advise(IntPtr p, out uint c);
    void Unadvise(uint c);
    void SetOptions(uint fos);
    void GetOptions(out uint fos);
    void SetDefaultFolder(IShellItem si);
    void SetFolder(IShellItem si);
    void GetFolder(out IShellItem si);
    void GetCurrentSelection(out IShellItem si);
    void SetFileName([MarshalAs(UnmanagedType.LPWStr)] string n);
    void GetFileName([MarshalAs(UnmanagedType.LPWStr)] out string n);
    void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string t);
    void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)] string t);
    void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)] string t);
    void GetResult(out IShellItem si);
  }
  [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
  static extern void SHCreateItemFromParsingName(string path, IntPtr pbc, ref Guid riid, out IShellItem item);
  public static string Sec(IntPtr sahip, string baslangic) {
    IFileOpenDialog d = (IFileOpenDialog)new FileOpenDialogRCW();
    uint o; d.GetOptions(out o);
    d.SetOptions(o | 0x20 | 0x40);  // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
    d.SetTitle("Konsol hangi klasorde acilsin?");
    d.SetOkButtonLabel("Bu klasorde ac");
    if (!String.IsNullOrEmpty(baslangic)) {
      try {
        Guid g = new Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE");
        IShellItem k; SHCreateItemFromParsingName(baslangic, IntPtr.Zero, ref g, out k);
        d.SetFolder(k);
      } catch (Exception) { }
    }
    int hr = d.Show(sahip);
    if (hr != 0) return "";
    IShellItem s; d.GetResult(out s);
    string yol; s.GetDisplayName(0x80058000, out yol);  // SIGDN_FILESYSPATH
    return yol;
  }
}
"@
if ($env:OFIS_GOZAT_DENE) { [Console]::Write('derlendi'); exit 0 }
$f = New-Object System.Windows.Forms.Form
$f.TopMost = $true; $f.ShowInTaskbar = $false; $f.Opacity = 0
$f.StartPosition = 'CenterScreen'; $f.Show(); $f.Activate()
$b = $env:OFIS_GOZAT_BASLANGIC
if (-not $b) { $b = [Environment]::GetFolderPath('Desktop') }
$yol = [OfisKlasorSec]::Sec($f.Handle, $b)
$f.Close()
[Console]::OutputEncoding = [Text.Encoding]::UTF8
[Console]::Write($yol)
