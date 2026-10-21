param([ValidateSet('setup','status','self-test')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.ComponentModel;
public static class MeshCredentials {
 [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
 public struct Credential {
  public uint Flags, Type;
  public string TargetName, Comment;
  public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
  public uint CredentialBlobSize;
  public IntPtr CredentialBlob;
  public uint Persist, AttributeCount;
  public IntPtr Attributes;
  public string TargetAlias, UserName;
 }
 [DllImport("advapi32.dll", EntryPoint="CredWriteW", CharSet=CharSet.Unicode, SetLastError=true)]
 static extern bool Write(ref Credential credential, uint flags);
 [DllImport("advapi32.dll", EntryPoint="CredReadW", CharSet=CharSet.Unicode, SetLastError=true)]
 static extern bool Read(string target, uint type, uint flags, out IntPtr credential);
 [DllImport("advapi32.dll", EntryPoint="CredDeleteW", CharSet=CharSet.Unicode, SetLastError=true)]
 static extern bool Delete(string target, uint type, uint flags);
 [DllImport("advapi32.dll")] static extern void CredFree(IntPtr ptr);
 public static void Store(string target, string user, System.Security.SecureString password) {
  IntPtr blob=Marshal.SecureStringToCoTaskMemUnicode(password);
  try {
   Credential c=new Credential(); c.Type=1; c.TargetName=target;
   c.UserName=user; c.Persist=2; c.CredentialBlob=blob;
   c.CredentialBlobSize=(uint)(password.Length*2);
   c.Comment="MESH homework login for current Windows user";
   if(!Write(ref c,0)) throw new Win32Exception(Marshal.GetLastWin32Error());
  } finally { Marshal.ZeroFreeCoTaskMemUnicode(blob); }
 }
 public static bool Exists(string target) {
  IntPtr ptr;
  if(!Read(target,1,0,out ptr)) {
   int error=Marshal.GetLastWin32Error();
   if(error==1168) return false;
   throw new Win32Exception(error);
  }
  try { return true; } finally { CredFree(ptr); }
 }
 public static void SelfTest() {
  string target="mesh-homework/test/"+Guid.NewGuid().ToString();
  var password=new System.Security.SecureString();
  foreach(char ch in "synthetic-value") password.AppendChar(ch);
  try {
   Store(target,"synthetic-user",password);
   IntPtr ptr;
   if(!Read(target,1,0,out ptr)) throw new Win32Exception(Marshal.GetLastWin32Error());
   try {
    Credential c=(Credential)Marshal.PtrToStructure(ptr,typeof(Credential));
    if(c.UserName!="synthetic-user" || Marshal.PtrToStringUni(c.CredentialBlob,(int)c.CredentialBlobSize/2)!="synthetic-value")
     throw new Exception("Credential round-trip failed");
   } finally { CredFree(ptr); }
  } finally { password.Dispose(); Delete(target,1,0); }
  if(Exists(target)) throw new Exception("Synthetic credential cleanup failed");
 }
}
'@
$target = 'mesh-homework/school.mos.ru'
switch ($Action) {
 'status' { if ([MeshCredentials]::Exists($target)) { 'credentials: saved' } else { 'credentials: missing' } }
 'self-test' { [MeshCredentials]::SelfTest(); 'Credential Manager synthetic round-trip: passed' }
 'setup' {
  $credential = Get-Credential -Message 'MESH: enter your mos.ru login and password. Saved in Windows Credential Manager for this Windows account.'
  if ($null -eq $credential) { 'credentials: cancelled'; exit 0 }
  if ([string]::IsNullOrWhiteSpace($credential.UserName) -or $credential.Password.Length -eq 0) { throw 'Login and password are required.' }
  [MeshCredentials]::Store($target, $credential.UserName, $credential.Password)
  $credential.Password.Dispose()
  $credential = $null
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.MessageBox]::Show('Saved in Windows Credential Manager. You can close this window.','MESH') | Out-Null
 }
}
