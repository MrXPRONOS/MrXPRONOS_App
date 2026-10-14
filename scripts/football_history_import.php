<?php
declare(strict_types=1);
/**
 * Mr XPRONOS: historical fixture collector (CLI only).
 * Sources: public-domain OpenFootball JSON and freely available Football-Data CSV.
 * Fixed endpoint templates, no credential extraction, login automation or CAPTCHA bypass.
 * Raw downloaded datasets are NOT committed or published.
 *
 * php scripts/football_history_import.php --source=both --seasons=2024-25,2025-26,2026-27 --out=/tmp/history.jsonl --max-files=36
 */
if (PHP_SAPI !== 'cli') { http_response_code(403); exit(1); }
$opts = getopt('', ['source::', 'seasons::', 'out::', 'max-files::', 'self-test']);
$source = (string)($opts['source'] ?? 'both');
$seasons = array_filter(array_map('trim', explode(',', (string)($opts['seasons'] ?? '2023-24,2024-25,2025-26,2026-27'))));
$out = (string)($opts['out'] ?? (sys_get_temp_dir().'/mrxpronos-history.jsonl'));
$maxFiles = max(1, min(120, (int)($opts['max-files'] ?? 48)));
$openLeagues = [
    'en.1' => 'Premier League', 'en.2' => 'Championship',
    'de.1' => 'Bundesliga', 'es.1' => 'La Liga',
    'it.1' => 'Serie A', 'fr.1' => 'Ligue 1',
];
$csvLeagues = ['E0'=>'Premier League','E1'=>'Championship','D1'=>'Bundesliga','SP1'=>'La Liga','I1'=>'Serie A','F1'=>'Ligue 1'];

function record(string $provider, string $season, string $league, string $date, string $home, string $away, int $hg, int $ag): ?array {
    $date = trim($date);
    $home = trim($home);
    $away = trim($away);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $date) || !checkdate((int)substr($date, 5, 2), (int)substr($date, 8, 2), (int)substr($date, 0, 4))) return null;
    if ($home === '' || $away === '' || $home === $away || $hg < 0 || $ag < 0 || $hg > 30 || $ag > 30) return null;
    $identity = implode('|', [$provider, $season, $league, $date, $home, $away]);
    return [
        'source' => $provider, 'source_id' => hash('sha256', $identity),
        'season' => $season, 'league' => $league, 'match_date' => $date,
        'home_team' => $home, 'away_team' => $away, 'home_score' => $hg,
        'away_score' => $ag, 'status' => 'finished',
        'kickoff_utc' => null, 'time_precision' => 'day',
        'historical_only' => true,
    ];
}
function parseOpen(string $body, string $season, string $league): array {
    $payload = json_decode($body, true);
    if (!is_array($payload) || !isset($payload['matches']) || !is_array($payload['matches'])) throw new RuntimeException('OpenFootball schema not recognized');
    $records = [];
    foreach ($payload['matches'] as $match) {
        if (!is_array($match)) continue;
        $ft = $match['score']['ft'] ?? null;
        if (!is_array($ft) || count($ft) !== 2 || !is_numeric($ft[0]) || !is_numeric($ft[1])) continue;
        $r = record('openfootball', $season, $league, (string)($match['date'] ?? ''), (string)($match['team1'] ?? ''), (string)($match['team2'] ?? ''), (int)$ft[0], (int)$ft[1]);
        if ($r !== null) $records[] = $r;
    }
    return $records;
}
function parseCsv(string $body, string $season, string $league): array {
    $stream = fopen('php://temp', 'w+');
    if ($stream === false) throw new RuntimeException('Temp stream unavailable');
    fwrite($stream, $body);
    rewind($stream);
    $headers = fgetcsv($stream);
    if (!is_array($headers)) { fclose($stream); return []; }
    $headers = array_map(static fn($h) => trim(preg_replace('/^\xEF\xBB\xBF/', '', (string)$h)), $headers);
    if (count(array_intersect(['Date','HomeTeam','AwayTeam','FTHG','FTAG'], $headers)) !== 5) {
        fclose($stream); throw new RuntimeException('CSV schema not recognized');
    }
    $rows = [];
    while (($cells = fgetcsv($stream)) !== false) {
        if (count($cells) !== count($headers)) continue;
        $row = array_combine($headers, $cells);
        if (!is_array($row) || !ctype_digit(trim((string)$row['FTHG'])) || !ctype_digit(trim((string)$row['FTAG']))) continue;
        $rawDate = trim((string)$row['Date']);
        $dt = DateTimeImmutable::createFromFormat('!d/m/Y', $rawDate, new DateTimeZone('UTC'));
        if ($dt === false) $dt = DateTimeImmutable::createFromFormat('!d/m/y', $rawDate, new DateTimeZone('UTC'));
        if ($dt === false) continue;
        $r = record('football_data', $season, $league, $dt->format('Y-m-d'), (string)$row['HomeTeam'], (string)$row['AwayTeam'], (int)$row['FTHG'], (int)$row['FTAG']);
        if ($r !== null) $rows[] = $r;
    }
    fclose($stream);
    return $rows;
}
function download(string $url): string {
    $host = parse_url($url, PHP_URL_HOST);
    if (!in_array($host, ['raw.githubusercontent.com', 'www.football-data.co.uk'], true)) throw new RuntimeException('Disallowed host');
    $context = stream_context_create(['http'=>[
        'method'=>'GET', 'timeout'=>20, 'ignore_errors'=>true, 'follow_location'=>0,
        'header'=>"User-Agent: MrXPRONOS-history-research/1.0\r\nAccept: application/json,text/csv,*/*\r\n",
    ]]);
    $body = @file_get_contents($url, false, $context);
    $status = 0;
    foreach (($http_response_header ?? []) as $line) {
        if (preg_match('/^HTTP\/[\d.]+\s+(\d{3})/', $line, $m)) $status = (int)$m[1];
    }
    if ($status !== 200 || !is_string($body) || strlen($body) > 12000000) throw new RuntimeException('HTTP '.$status.' (unavailable or over size limit)');
    return $body;
}
if (array_key_exists('self-test', $opts)) {
    $sample = '{"matches":[{"date":"2025-01-14","team1":"A","team2":"B","score":{"ft":[2,1]}},{"date":"2025-01-16","team1":"A","team2":"C"}]}';
    $a = parseOpen($sample, '2024-25', 'Premier League');
    $b = parseCsv("Date,HomeTeam,AwayTeam,FTHG,FTAG\n14/01/2025,A,B,2,1\n", '2024-25', 'Premier League');
    if (count($a) !== 1 || count($b) !== 1 || $a[0]['home_score'] !== 2 || $b[0]['match_date'] !== '2025-01-14') exit(1);
    echo "HISTORY_PHP_SELF_TEST_OK\n"; exit(0);
}
if (!in_array($source, ['both','openfootball','football-data'], true)) { fwrite(STDERR,"Invalid source\n"); exit(2); }
foreach ($seasons as $season) {
    if (!preg_match('/^20\d{2}-(?:20)?\d{2}$/', $season)) { fwrite(STDERR,"Invalid season: ".$season."\n"); exit(2); }
    [$begin, $end] = explode('-', $season);
    $finalYear = strlen($end) === 2 ? 2000 + (int)$end : (int)$end;
    if ($finalYear !== (int)$begin+1) { fwrite(STDERR,"Non-consecutive season\n"); exit(2); }
}
$dir = dirname($out);
if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) throw new RuntimeException('Cannot create output dir');
$tmp = $out.'.tmp';
$fd = fopen($tmp, 'wb');
if ($fd === false) throw new RuntimeException('Cannot write output');
chmod($tmp, 0600);
$requests = 0; $count = 0; $failures = []; $ids = [];
foreach ($seasons as $season) {
    $code = substr($season,2,2).substr($season,-2);
    foreach (['openfootball','football-data'] as $provider) {
        if ($source !== 'both' && $source !== $provider) continue;
        $leagues = $provider === 'openfootball' ? $openLeagues : $csvLeagues;
        foreach ($leagues as $division => $league) {
            if ($requests >= $maxFiles) break 3;
            $url = $provider === 'openfootball'
                ? "https://raw.githubusercontent.com/openfootball/football.json/master/{$season}/{$division}.json"
                : "https://www.football-data.co.uk/mmz4281/{$code}/{$division}.csv";
            if ($requests > 0) usleep(1100000); // respectful, no anti-bot bypass
            $requests++;
            try {
                $body = download($url);
                $rows = $provider === 'openfootball' ? parseOpen($body, $season, $league) : parseCsv($body, $season, $league);
                foreach ($rows as $r) {
                    if (isset($ids[$r['source_id']])) continue;
                    $ids[$r['source_id']] = true;
                    fwrite($fd, json_encode($r, JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)."\n");
                    $count++;
                }
            } catch (Throwable $e) {
                $failures[] = $provider.':'.$season.':'.$division.':'.$e->getMessage();
            }
        }
    }
}
fclose($fd);
if (!rename($tmp, $out)) throw new RuntimeException('Cannot finalize archive');
echo json_encode(['files_attempted'=>$requests,'rows'=>$count,'failed_files'=>$failures,'out'=>$out], JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)."\n";
if ($count === 0) exit(1);
