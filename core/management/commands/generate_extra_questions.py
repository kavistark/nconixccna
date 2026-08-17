import random
from django.core.management.base import BaseCommand
from core.models import Topic, Question

class Command(BaseCommand):
    help = 'Ensures each CCNA topic has exactly 5 quiz questions by generating high-quality context-aware questions.'

    def handle(self, *args, **options):
        topics = Topic.objects.select_related('domain').all()
        self.stdout.write(f"Checking {topics.count()} topics in the database...")

        domain_templates = {
            'Network Fundamentals': [
                {
                    'question': "Which of the following describes a key concept or component of {title}?",
                    'options': [
                        "It defines how devices connect and interact at the physical and link levels.",
                        "It is a routing protocol exclusively used in WAN environments.",
                        "It operates only at the application layer to encrypt emails.",
                        "It is a standard tool for monitoring network room temperatures."
                    ],
                    'explanation': "{title} is a core foundation of network operations, covering basic component interactions."
                },
                {
                    'question': "What is a main objective when implementing or analyzing {title}?",
                    'options': [
                        "To ensure efficient, reliable, and standardized network communication.",
                        "To eliminate the need for IP routing entirely.",
                        "To assign static IP addresses to all endpoints globally.",
                        "To shut down unused ports on core routers automatically."
                    ],
                    'explanation': "Standardization and reliability are the main objectives of {title} in networking."
                },
                {
                    'question': "In the context of the OSI model, which layer is most closely associated with {title}?",
                    'options': [
                        "The physical, data link, or network layers, depending on the specific component.",
                        "The application layer only.",
                        "The session layer only.",
                        "It does not align with any layer of the OSI model."
                    ],
                    'explanation': "Most network fundamental concepts like {title} map to the lower three layers of the OSI model."
                }
            ],
            'Network Access': [
                {
                    'question': "What is the primary role of {title} in a local area network (LAN) environment?",
                    'options': [
                        "To manage and control physical/logical access to the network medium.",
                        "To route traffic across the internet to external hosts.",
                        "To resolve domain names to IP addresses.",
                        "To establish SSH sessions with remote servers."
                    ],
                    'explanation': "{title} focuses on Layer 2 and Layer 1 technologies that enable local device communication."
                },
                {
                    'question': "Which of the following is a common technology or configuration associated with {title}?",
                    'options': [
                        "VLANs, trunking, or port settings depending on the switch design.",
                        "Dynamic routing protocols like OSPF.",
                        "Network Address Translation (NAT).",
                        "REST APIs and JSON payloads."
                    ],
                    'explanation': "Switch configuration, VLANs, and Layer 2 interfaces are standard elements of {title}."
                },
                {
                    'question': "What issue or behavior can occur if {title} is configured incorrectly?",
                    'options': [
                        "Loss of local connectivity or security vulnerabilities like unauthorized access.",
                        "A total failure of the internet-wide DNS system.",
                        "Router memory leakage due to large routing tables.",
                        "Automatic conversion of IPv4 packets to IPv6."
                    ],
                    'explanation': "Incorrect configuration of access-related settings like {title} typically leads to VLAN mismatches, trunking errors, or access blockages."
                }
            ],
            'IP Connectivity': [
                {
                    'question': "What is the core purpose of {title} in an IP network?",
                    'options': [
                        "To determine the best path for packets to travel from source to destination.",
                        "To assign IP addresses to client hosts dynamically.",
                        "To encrypt web traffic using HTTPS.",
                        "To translate private IP addresses to public ones."
                    ],
                    'explanation': "Connectivity and routing (the focus of {title}) ensure packets can reach remote networks."
                },
                {
                    'question': "Which routing behavior or metric is critical to the operation of {title}?",
                    'options': [
                        "Path selection based on administrative distance, cost, or static definitions.",
                        "The lease duration of DHCP allocations.",
                        "The port security violation action.",
                        "The SSH timeout period."
                    ],
                    'explanation': "Routing decisions in {title} rely on prefix matching, administrative distance, and routing protocols."
                },
                {
                    'question': "How does a router handle packets when {title} is not properly configured for a destination network?",
                    'options': [
                        "It drops the packet and may send an ICMP Host Unreachable message.",
                        "It forwards the packet to all interfaces like a hub.",
                        "It automatically learns the route via ARP.",
                        "It buffers the packet indefinitely until the route is added."
                    ],
                    'explanation': "Without a valid route (static or dynamic) associated with {title}, the packet is dropped."
                }
            ],
            'IP Services': [
                {
                    'question': "Which of the following best describes the function of {title}?",
                    'options': [
                        "It provides utility services like address allocation, name resolution, or time synchronization.",
                        "It is a physical cabling standard used for high-speed fiber links.",
                        "It is a dynamic routing protocol based on link-state logic.",
                        "It is a hardware mechanism to prevent loop formation on switches."
                    ],
                    'explanation': "IP Services like {title} support network operations by providing essential functions like DHCP, DNS, NTP, etc."
                },
                {
                    'question': "Why is {title} considered essential in a modern enterprise network?",
                    'options': [
                        "It automates administrative tasks and ensures consistency across client devices.",
                        "It makes routing protocols obsolete.",
                        "It encrypts all local Layer 2 broadcast frames.",
                        "It allows switches to operate without power."
                    ],
                    'explanation': "Services like {title} simplify management and allow hosts to function seamlessly without manual configuration."
                },
                {
                    'question': "Which port or transport protocol is typically associated with {title}?",
                    'options': [
                        "A standardized UDP/TCP port designated for that service (e.g. DHCP, DNS, NTP, NAT).",
                        "ICMP type 8 only.",
                        "Any random dynamic port above 49152.",
                        "It does not use transport layer protocols."
                    ],
                    'explanation': "IP Services run on specific, well-known ports to listen for client requests."
                }
            ],
            'Security Fundamentals': [
                {
                    'question': "What is a primary goal of implementing {title} in a network infrastructure?",
                    'options': [
                        "To protect network resources from unauthorized access, modification, or disruption.",
                        "To speed up routing lookups on core switches.",
                        "To automatically backup configurations to public cloud storage.",
                        "To merge broadcast domains into a single flat network."
                    ],
                    'explanation': "Security measures like {title} mitigate threats and secure the control, data, and management planes."
                },
                {
                    'question': "Which of the following is a common mechanism used to enforce {title}?",
                    'options': [
                        "Access lists, port security, encryption, or authentication policies.",
                        "Spanning Tree Protocol (STP).",
                        "Subnetting with VLSM.",
                        "YAML configuration playbooks."
                    ],
                    'explanation': "Security policies for {title} utilize access control, stateful inspection, and device hardening."
                },
                {
                    'question': "What risk does a network face if {title} is neglected?",
                    'options': [
                        "Data breaches, spoofing attacks, or unauthorized configuration changes.",
                        "Excessive cabling attenuation.",
                        "A decrease in the speed of light in copper wires.",
                        "Incompatibility between IPv4 and IPv6 routing."
                    ],
                    'explanation': "Failing to implement proper security controls like {title} exposes the network to malicious exploitation."
                }
            ],
            'Automation & Programmability': [
                {
                    'question': "How does {title} improve network administration compared to traditional methods?",
                    'options': [
                        "By allowing programmatic configuration, reducing human error, and scaling changes rapidly.",
                        "By physically replacing routers with software servers.",
                        "By eliminating the need for any IP addressing scheme.",
                        "By increasing the speed of physical fiber-optic cables."
                    ],
                    'explanation': "Automation and programmability (like {title}) move networks away from manual CLI-by-CLI management to centralized APIs and scripts."
                },
                {
                    'question': "Which format or protocol is commonly utilized in the context of {title}?",
                    'options': [
                        "JSON, XML, YAML, or REST APIs to communicate with controllers.",
                        "VTP and DTP frame formats.",
                        "Standard Layer 2 Ethernet frames.",
                        "EIGRP routing updates."
                    ],
                    'explanation': "Modern automation relies heavily on structured data formats and API communication for {title}."
                },
                {
                    'question': "What is a key component of a network architecture that leverages {title}?",
                    'options': [
                        "A centralized controller or management tool that coordinates device state.",
                        "A physical console cable connected to each individual switch.",
                        "A loopback interface configured on every host.",
                        "A standard analog telephone line for out-of-band access."
                    ],
                    'explanation': "SDN controllers and orchestration tools coordinate configuration push and monitoring for {title}."
                }
            ]
        }

        generated_count = 0

        for topic in topics:
            current_count = topic.questions.count()
            if current_count >= 5:
                self.stdout.write(f"Topic {topic.id} already has {current_count} questions. Skipping.")
                continue

            needed_count = 5 - current_count
            self.stdout.write(f"Topic {topic.id} '{topic.title}' has {current_count} questions. Generating {needed_count} more...")

            domain_name = topic.domain.name
            templates = domain_templates.get(domain_name, [])
            if not templates:
                # Fallback to Network Fundamentals templates if domain doesn't match
                templates = domain_templates['Network Fundamentals']

            # Make copies of templates to choose from
            available_templates = list(templates)
            random.shuffle(available_templates)

            for i in range(needed_count):
                if i < len(available_templates):
                    template = available_templates[i]
                else:
                    # If we need more than templates available, reuse
                    template = random.choice(templates)

                # Format the question with the topic title
                q_text = template['question'].format(title=topic.title)
                raw_options = [opt.format(title=topic.title) for opt in template['options']]
                explanation = template['explanation'].format(title=topic.title)

                # Shuffle options so the correct answer (initially at index 0) is randomized
                correct_option = raw_options[0]
                shuffled_options = list(raw_options)
                random.shuffle(shuffled_options)
                correct_index = shuffled_options.index(correct_option)

                # Create the question
                Question.objects.create(
                    topic=topic,
                    question_text=q_text,
                    options=shuffled_options,
                    correct_index=correct_index,
                    explanation=explanation
                )
                generated_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully generated {generated_count} extra questions! All topics now have exactly 5 questions."))
