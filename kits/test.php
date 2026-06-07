<?php
header('Content-Type: text/html; charset=UTF-8');

function status_line($label, $ok, $goodText = 'OK', $badText = 'PROBLEM') {
    $color = $ok ? 'green' : 'red';
    $text = $ok ? $goodText : $badText;
    echo "<p><strong>{$label}:</strong> <span style=\"color:{$color}\">{$text}</span></p>";
}

echo "<h1>Sandbox działa</h1>";
echo "<p><strong>PHP version:</strong> " . htmlspecialchars(PHP_VERSION, ENT_QUOTES, 'UTF-8') . "</p>";
echo "<p><strong>disable_functions:</strong> " . htmlspecialchars(ini_get('disable_functions'), ENT_QUOTES, 'UTF-8') . "</p>";
echo "<p><strong>allow_url_fopen:</strong> " . htmlspecialchars(ini_get('allow_url_fopen'), ENT_QUOTES, 'UTF-8') . "</p>";
echo "<p><strong>allow_url_include:</strong> " . htmlspecialchars(ini_get('allow_url_include'), ENT_QUOTES, 'UTF-8') . "</p>";
echo "<p><strong>sendmail_path:</strong> " . htmlspecialchars(ini_get('sendmail_path'), ENT_QUOTES, 'UTF-8') . "</p>";
echo "<p><strong>open_basedir:</strong> " . htmlspecialchars(ini_get('open_basedir'), ENT_QUOTES, 'UTF-8') . "</p>";

$disabledFunctions = ['exec', 'system', 'shell_exec', 'passthru', 'proc_open', 'popen', 'pcntl_exec', 'putenv', 'dl'];
echo "<h2>Test wyłączonych funkcji</h2>";
foreach ($disabledFunctions as $fn) {
    status_line($fn, !function_exists($fn), 'wyłączona', 'nadal dostępna');
}

echo "<h2>Test przechwycenia mail()</h2>";
$mailOk = mail('attacker@example.test', 'Sandbox test', 'To jest test przechwycenia mail().');
status_line('mail()', $mailOk, 'wywołane i przekazane do fake-sendmail', 'nie udało się wywołać');
echo "<p>Po teście w katalogu <code>logs/</code> powinien pojawić się plik <code>.eml</code>.</p>";
