#!/bin/sh
#
# Anyka camera settings writer.
#   PATCHED 2026-09-21: the stock loop wrote `$parameter=$(eval ...)` only when
#   the parameter appeared in the query, but for checkboxes that are UNCHECKED
#   the browser omits them entirely -> the value was reset to EMPTY, silently
#   wiping run_ftp/run_telnet (the security settings). Now an omitted parameter
#   keeps its existing value from gergesettings.txt.
#
if [[ -f /etc/jffs2/www/index.html ]]; then
    source /etc/jffs2/www/cgi-bin/header
else
    source /mnt/anyka_hack/web_interface/www/cgi-bin/header
fi
if [[ -f /tmp/token.txt ]] && [[ "$token" == "$(readline 1 /tmp/token.txt)" ]]; then
cat <<EOT
<!DOCTYPE html>
<html>
<head>
<title>Camera - WebUI</title>
<link rel="icon" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/styles.css">
</head>
<body>
<div class="topnav">
  <a href="/cgi-bin/webui?token=$token">Home</a>
  <a class="active" href="/cgi-bin/settings?token=$token">Settings</a>
  <a href="/cgi-bin/system?token=$token">System</a>
  <a href="/cgi-bin/events?token=$token">Events</a>
  <a href="/cgi-bin/login">Exit</a>
</div>
<section>

<div class="card">
<h2>Saving Done</h2>
Please reboot for the changes to take effect<br><br>
<button class="button" onclick="window.location.href='system?token=$token&command=reboot'">Reboot</button><br><br>
</div>
</section>

</body>
</html>
EOT

check1=$(echo $QUERY_STRING | grep day_night_invert)
check2=$(echo $QUERY_STRING | grep ir_invert)
check3=$(echo $QUERY_STRING | grep image_upside_down)
if [[ ${#check1} -gt 1 ]] && [[ ${#check2} -gt 1 ]] && [[ ${#check3} -gt 1 ]]; then
  if [[ $day_night_invert == 1 ]]; then
    if [[ $ir_invert == 1 ]]; then extra_args="-i 3"; else extra_args="-i 4"; fi
  else
    if [[ $ir_invert == 1 ]]; then extra_args="-i 2"; else extra_args="-i 1"; fi
  fi
  if [[ $image_upside_down == 1 ]]; then
    extra_args="\"$extra_args -u\""
  else
    extra_args="\"$extra_args\""
  fi
  QUERY_STRING="$QUERY_STRING extra_args=$extra_args"
fi

linecount=1
echo -n "" >data.tmp
linecountlimit=$(wc -l < /etc/jffs2/gergesettings.txt)
while [ $linecount -le $linecountlimit ]; do
    line=$(readline $linecount /etc/jffs2/gergesettings.txt)
    line=$(echo "$line" | awk '{$1=$1};1')
    if [[ ${line:0:1} == '#' ]] || [[ ${#line} -lt 1 ]]; then
      echo "$line" >>data.tmp
    else
      parameter="${line%%=*}"
      inquery=$(echo $QUERY_STRING | grep "$parameter=")
      if [[ ${#inquery} -gt 1 ]]; then
        echo "$parameter=$(eval 'echo $'$parameter)" >>data.tmp
      else
        echo "$line" >>data.tmp
      fi
    fi
    let linecount+=1
done
cp data.tmp /etc/jffs2/gergesettings.txt
if [[ -f /mnt/anyka_hack/gergesettings.txt ]]; then
  cp data.tmp /mnt/anyka_hack/gergesettings.txt
fi
else
    if [[ -f /etc/jffs2/www/index.html ]]; then
        source /etc/jffs2/www/cgi-bin/footer
    else
        source /mnt/anyka_hack/web_interface/www/cgi-bin/footer
    fi
fi
