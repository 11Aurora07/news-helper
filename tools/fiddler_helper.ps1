Add-Type -AssemblyName Microsoft.VisualBasic
Add-Type -AssemblyName System.Windows.Forms

$wshell = New-Object -ComObject WScript.Shell

function Show-Step($message) {
    [System.Windows.Forms.MessageBox]::Show(
        $message,
        "通知助手 - Fiddler 辅助",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

function Activate-Window($titlePart) {
    if (-not $wshell.AppActivate($titlePart)) {
        throw "找不到窗口: $titlePart"
    }
    Start-Sleep -Milliseconds 500
}

function Send-Keys($keys) {
    $wshell.SendKeys($keys)
    Start-Sleep -Milliseconds 500
}

try {
    Show-Step "脚本会先切到 Fiddler 并清空会话。请确保 Fiddler 和 微信 都已经打开。"

    Activate-Window "Fiddler"
    Send-Keys "^x"

    Show-Step "Fiddler 会话已清空。接下来会切到微信。请你在校园墙小程序里进入帖子列表页并手动下拉刷新一次。完成后点击确定。"

    Activate-Window "微信"

    [System.Windows.Forms.MessageBox]::Show(
        "请现在在微信小程序里打开校园墙列表，并执行一次下拉刷新。完成后点击“确定”。",
        "通知助手 - 等待刷新",
        [System.Windows.Forms.MessageBoxButtons]::OKCancel,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null

    Activate-Window "Fiddler"

    Show-Step "已经切回 Fiddler。现在请优先查看左侧列表里不是 servicewechat.com 的新请求，尤其是 Content-Type 为 application/json 的条目。"
}
catch {
    [System.Windows.Forms.MessageBox]::Show(
        $_.Exception.Message,
        "通知助手 - 运行失败",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}
