# Live Endpoints

- generated_at: 2026-03-14T04:27:00Z

| Surface | URL | Status | Notes |
|---|---|---|---|
| Observatory (live) | https://generous-ladder-twins-sims.trycloudflare.com | UP | Streamlit RNA observatory |
| Vast Jupyter | https://175.155.64.231:19808 | UP | notebook + terminal |
| Vast Portal (1111) | http://175.155.64.231:19121 | UP(auth) | instance portal |
| Vast TensorBoard (6006) | http://175.155.64.231:19448 | UP(auth) | tensorboard ingress |
| Vast Syncthing (8384) | http://175.155.64.231:19753 | UP(auth) | sync ingress |
| Vast SSH | ssh -i ~/.ssh/gpu_orchestra_ed25519 -p 19636 root@175.155.64.231 | UP | direct ssh |

## Tunnel note
Quick tunnel URLs rotate. Current observatory tunnel is valid now and should be treated as ephemeral.
