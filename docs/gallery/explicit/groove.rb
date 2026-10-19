use_bpm 100
live_loop :drums do
  sample :bd_haus, amp: 1.5
  sleep 0.5
  sample :sn_dolf, amp: 0.8
  sleep 0.5
end
live_loop :hats do
  sample :drum_cymbal_closed, amp: 0.4, rate: 1.2
  sleep 0.25
end
live_loop :bass do
  use_synth :tb303
  play (ring :e2, :e2, :g2, :a2).tick, release: 0.2, cutoff: rrand(60, 100)
  sleep 0.5
end
live_loop :keys do
  use_synth :prophet
  with_fx :reverb, room: 0.8 do
    play chord(:e4, :minor7), release: 1.5, amp: 0.4
  end
  sleep 2
end
