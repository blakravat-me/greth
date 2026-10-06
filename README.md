.
├── Makefile ✅
├── README.md
├── greth
│   ├── context.py
│   ├── core.py
│   ├── graph
│   │   └── ...
│   ├── prompts
│   │   ├── informant.md
│   │   ├── manager.md
│   │   └── operator.md
│   └── state.py
├── containers
│   └── Dockerfile ✅
├── docker-compose.yml ✅
├── greth_logging
│   └── logger.py ✅
├── helpers
│   ├── console.py ✅
│   └── docker.py ✅
├── llm
│   ├── adapter.py ✅
│   ├── helpers
│   │   ├── errors.py ✅
│   │   ├── http.py ✅
│   │   └── repair.py ✅
│   ├── providers
│   │   └── ollama.py ✅
│   ├── structured.py ✅
│   └── tools.py ✅
├── main.py
├── tools
│   ├── policy.py
│   └── process
│       ├── __init__.py
│       ├── proc.py
│       ├── proc_kill.py
│       ├── proc_output.py
│       └── proc_status.py
└── ui
    ├── renderer.py ✅
    ├── dynamic
    │   └── output.py ✅
    ├── static
    │   └── banner.py ✅
    ├── live
    │   ├── objective.py ✅
    │   ├── phase.py ✅
    │   └── usage.py ✅
    └── helpers
        └── ...





## FASE

- RECON
- EXPLOIT
- POST-EXPLOIT

## STATE

- OBSERVE
- ORIENT
- DECIDE
- ACT

## WORKFLOW

---
INPUT: target + specialist + user_input

FASE: RECON
STATE: OBSERVE -> ORIENT -> DECIDE -> ACT
PROMPT: prompts/recon/<O-O-D-A>.md

TOOLS: 
  - set_objective(objective="Service Discovery & Port Scan", plan=["..."]) -> JSON
  - bash(command="nmap -sV google.com", session="nmap_scan", timeout=20, background=False, is_input=False) -> JSON
  - set_service(port="21", service="vsftpd 2.3.4") -> JSON
  - set_service(port="22") -> JSON
  - ...others

STORAGE:
{
  "objectives":[
    {
      "id": "2",
      "objective": "Service Discovery & Port Scan",
      "plans": [
        {
          "plan": "melakukan ping ke google.com",
          "done": true
        },
        {
          "plan": "cek ports dan services",
          "done": true
        },
        {
          "plan": "cek versi dengan searchsploit",
          "done": false
        }
      ],
      "done": false
    }
  ],
  "findings": {
    "services": [
      {
        "21": "vsftpd 2.3.4"
      },
      {
        "22": "filtered"
      },
      {
        "3306": "filtered"
      }
    ],
    "tech": [
      "mysql",
      "nodeJS"
    ],
    "errors": [
      {
        "source": "https://google.com/mn?data='5",
        "errors": [
            "SQL syntax error: unterminated string literal near '5''"
        ]
      }
    ],
    ...others
  }
}
---

## USER INTERFACE

- OBJECTIVES
- PLANS
- COMMAND
- OUTPUT
- CONTEXT + NEXT ACTION

---
• Objective (1 Active, 1 Pending, 1 Done)
  ✓ <OBJ-1>
  ▣ Service Discovery & Port Scan
  ◻ <0BJ-3>

• OBJ-2 OPPLAN:
  - melakukan ping ke google.com
  - cek ports dan services
  - cek versi dengan searchsploit

• CONTEXT: Sekarang saya akan megecek status target telebih dahulu.

┌──(root㉿sandbox)-[/workspace]
└─# ping -c google.com
PING google.com (74.125.130.100) 56(84) bytes of data.
64 bytes from sb-in-f100.1e100.net (74.125.130.100): icmp_seq=1 ttl=105 time=27.3 ms
64 bytes from sb-in-f100.1e100.net (74.125.130.100): icmp_seq=2 ttl=105 time=26.6 ms
64 bytes from sb-in-f100.1e100.net (74.125.130.100): icmp_seq=3 ttl=105 time=26.9 ms

--- google.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2004ms
rtt min/avg/max/mdev = 26.580/26.914/27.271/0.282 ms

• CONTEXT: Good! google.com dapat diakses. saya akan melakukan port scanning.

┌──(root㉿sandbox)-[/workspace]
└─# nmap -sV google.com
<nmap_result>

• CONTEXT: Perfect! ditemuakan port 21 service vsftpd 2.3.4. Akan saya cek versi terhadap public exploit.
---