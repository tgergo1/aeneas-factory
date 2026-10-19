## Render Sonic Pi code to a WAV file: code in, audio out, nothing played aloud.
##
##   ruby sonicpi_record.rb -o OUT.wav -d SECONDS [-f FILE.rb | -e CODE] [-s SEED] [-w WORKDIR]
##
## Run it with the Ruby inside Sonic Pi.app. Sonic Pi 5's own headless-record.rb plays through the sound
## card and sends its record commands over UDP, which its engine (SuperSonic 0.71) no longer listens to;
## and the engine's --headless mode stops recording after about a second. So:
## - Sonic Pi gets a throwaway home (SONIC_PI_HOME), so the user's ~/.sonic-pi is never touched;
## - its main mixer is muted before any code runs, so nothing reaches the speakers;
## - the code runs inside `with_fx :record` into a buffer (the FX sits before the mixer, so the take is
##   full level), and the engine saves the buffer itself. The block then waits out the take, since
##   live_loops return at once and the FX lasts only as long as its block.
## Rendering is real time: a 30 s piece takes about 30 s plus the boot (5-10 s).
require "fileutils"
require "tmpdir"

APP = File.expand_path(ENV["AEN_SONIC_PI_APP"] || "/Applications/Sonic Pi.app")
RES = File.join(APP, "Contents", "Resources")
USAGE = "Usage: sonicpi_record.rb -o OUT.wav -d SECONDS [-f FILE.rb | -e CODE] [-s SEED] [-w WORKDIR]"

out = secs = code = seed = work = nil
args = ARGV.dup
take = ->(flag) { args.shift or abort("#{flag} needs a value\n#{USAGE}") }
until args.empty?
  case (flag = args.shift)
  when "-o" then out = File.expand_path(take.(flag))
  when "-d" then secs = take.(flag).to_f
  when "-f" then code = File.read(take.(flag))
  when "-e" then code = take.(flag)
  when "-s" then seed = Integer(take.(flag))
  when "-w" then work = File.expand_path(take.(flag))
  when "-h", "--help" then puts USAGE; exit 0
  else abort "Unknown argument: #{flag}\n#{USAGE}"
  end
end
abort USAGE unless out && secs
abort "the length must be between 0.5 and 600 seconds" unless secs >= 0.5 && secs <= 600
code = STDIN.read if code.nil?
abort "no code (use -f, -e or stdin)" if code.strip.empty?
abort "Sonic Pi is not installed at #{APP} (brew install --cask sonic-pi)" unless File.directory?(RES)

work ||= Dir.mktmpdir("aen-sonic-pi")
ENV["SONIC_PI_HOME"] = File.join(work, "home")
ENV.delete("SONIC_PI_ROOT")
FileUtils.mkdir_p(ENV["SONIC_PI_HOME"])
Dir.chdir(work)  # Sonic Pi asks for its working folder; in a sandbox only this one is readable

require File.join(RES, "app", "server", "ruby", "bin", "headless_boot")

# never outlive a stuck boot or a run that does not end
Thread.new { sleep secs + 90; warn "sonic-pi: timed out"; exit! 3 }

boot = SonicPi::HeadlessBoot.new.boot!
boot.mute!  # silence at the speakers; the record FX is before the mixer
sleep 0.5
FileUtils.mkdir_p(File.dirname(out))
FileUtils.rm_f(out)  # never mistake an old file for this take
take_name = ":aen_take_#{Process.pid}"
body = (seed ? "use_random_seed #{seed}\n" : "") + code
# wait out the take inside the block, in seconds whatever tempo the code set
boot.run("__aen_take = buffer(#{take_name}, #{secs})\nwith_fx :record, buffer: __aen_take do\n#{body}\n" \
         "with_bpm 60 do\n  sleep #{secs + 1}\nend\nend\n")
sleep secs + 0.5
boot.run("buffer_save(buffer(#{take_name}, #{secs}), #{out.inspect})")
60.times { break if File.exist?(out) && File.size(out) > 1000; sleep 0.25 }
boot.stop_all
sleep 0.5
unless boot.errors.empty?
  warn "sonic-pi errors: #{boot.errors.join(' | ')}"
  exit 2
end
unless File.exist?(out) && File.size(out) > 1000
  warn "sonic-pi: nothing was recorded"
  exit 1
end
puts "wrote #{out}"
exit 0
