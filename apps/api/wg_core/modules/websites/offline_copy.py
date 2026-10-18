"""Website copy without AI: free, instant, same output for the same domain (re-runs are stable).

Written per industry group of the 15 templates, from the Sheet facts only (company name, city/state). Every variant is
plain and factual: no awards, clients, years, numbers, ratings or guarantees — and the result still goes through
content_check.problems() like AI copy. The variant of each block is picked from the domain name, so sites built for
different companies do not read the same, while the same company always gets the same text.
"""
import random

from .templates import BY_ID

# group → (business noun, services [(title, description)], approach words)
GROUPS = {
    "Doanh nghiệp & Dịch vụ": ("business services company", [
        ("Business Consulting", "Practical advice on day-to-day operations, planning and organisation, adapted to the size and needs of each client."),
        ("Project Coordination", "Clear coordination of tasks, suppliers and schedules so that each project moves forward in an orderly way."),
        ("Administrative Support", "Help with the routine administrative work that keeps a company running smoothly from one week to the next."),
        ("Commercial Services", "Commercial support for companies that want a dependable local partner for their regular business needs."),
        ("Client Service", "A direct point of contact who listens, answers questions and follows each request through to completion."),
    ], "organised and dependable"),
    "Xây dựng & Kiến trúc": ("construction company", [
        ("Construction Services", "Building work carried out with care for safety, materials and the agreed plan from the first day on site."),
        ("Renovation & Remodeling", "Renovation of homes and commercial spaces, from small improvements to complete remodeling projects."),
        ("Project Planning", "Planning of scope, materials and schedule together with the client before any work begins."),
        ("Maintenance & Repairs", "Repairs and maintenance that keep buildings in good condition and prevent small problems from growing."),
        ("Site Management", "Daily management of the work site, suppliers and teams so the project stays organised."),
    ], "careful and well planned"),
    "Công nghệ": ("technology company", [
        ("Technology Consulting", "Advice on choosing and using the right tools and systems for the way a business actually works."),
        ("Software & Systems", "Setup and support of software and business systems, with attention to reliability and ease of use."),
        ("Digital Services", "Digital services that help companies present themselves and work more efficiently online."),
        ("Technical Support", "Responsive technical support that helps teams solve problems and keep working."),
        ("Data & Infrastructure", "Organisation of data and infrastructure so information stays available, safe and easy to find."),
    ], "clear and practical"),
    "Truyền thông": ("media and production company", [
        ("Content Production", "Production of video, photo and written content prepared for each client's audience and channels."),
        ("Media Services", "Media services from first idea to final delivery, with clear communication at every step."),
        ("Creative Direction", "Creative direction that keeps every piece of content consistent with the client's message."),
        ("Post-Production", "Editing and finishing work that turns raw material into polished, ready-to-publish content."),
        ("Event Coverage", "Coverage of events and activities, prepared in advance with the client."),
    ], "creative and well organised"),
    "Y tế & Làm đẹp": ("health and wellness business", [
        ("Personal Care", "Care services delivered in a calm, clean and welcoming environment, with attention to each person."),
        ("Consultations", "Unhurried consultations to understand each client's needs before any treatment or service."),
        ("Wellness Services", "Services focused on comfort and well-being, explained clearly before they begin."),
        ("Treatment Planning", "A simple plan agreed with the client, so it is always clear what comes next."),
        ("Follow-Up Care", "Follow-up after each visit to answer questions and adjust the plan when needed."),
    ], "attentive and respectful"),
    "Pháp lý & Tài chính": ("professional services firm", [
        ("Advisory Services", "Clear, careful advice that helps clients understand their options before they decide."),
        ("Document Preparation", "Preparation and review of documents with attention to detail and to each client's situation."),
        ("Financial Services", "Support with financial matters, explained in plain language and organised step by step."),
        ("Case Coordination", "Organised handling of each matter, with regular updates and a clear record of what was done."),
        ("Client Consultations", "Confidential consultations to listen first and recommend a sensible way forward."),
    ], "careful and confidential"),
    "Giáo dục": ("education and training provider", [
        ("Courses & Classes", "Courses and classes planned around clear goals and the pace of each group of learners."),
        ("Training Programs", "Practical training programs for individuals and organisations that want to build new skills."),
        ("Tutoring", "Individual and small-group tutoring with attention to each learner's progress."),
        ("Learning Materials", "Well organised learning materials that support every lesson and make review easier."),
        ("Student Guidance", "Guidance for students and families on choosing the right program and next steps."),
    ], "patient and encouraging"),
    "Du lịch": ("travel company", [
        ("Trip Planning", "Planning of trips around each traveller's interests, dates and budget."),
        ("Travel Arrangements", "Arrangement of transport, accommodation and activities so travellers can focus on the journey."),
        ("Group Travel", "Organisation of group trips with clear schedules and one point of contact."),
        ("Local Experiences", "Suggestions for local experiences that suit the traveller and the destination."),
        ("Travel Support", "Support before and during the trip for questions and changes to plans."),
    ], "friendly and well organised"),
    "Thương mại": ("trading and retail business", [
        ("Product Supply", "Supply of quality products for businesses and customers, with clear information about each item."),
        ("Wholesale & Retail", "Sales to retail customers and to businesses that need a regular, dependable supplier."),
        ("Order Handling", "Careful handling of orders, from the first request to delivery or pick-up."),
        ("Product Advice", "Help choosing the right products, based on what each customer actually needs."),
        ("Customer Service", "Friendly customer service before and after every purchase."),
    ], "honest and dependable"),
    "Môi trường & Nông nghiệp": ("environmental and agricultural business", [
        ("Environmental Services", "Services carried out with respect for the environment and for local rules."),
        ("Agricultural Services", "Agricultural work planned around the land, the season and the client's goals."),
        ("Collection & Handling", "Organised collection and handling of materials, done safely and on schedule."),
        ("Land & Site Care", "Care of land and sites so they stay productive, clean and well maintained."),
        ("Consulting & Planning", "Practical planning for projects that need to balance productivity and care for nature."),
    ], "responsible and practical"),
}
DEFAULT_GROUP = "Doanh nghiệp & Dịch vụ"

WHY = [
    ("Clear Communication", "You always know what is planned, what is done and what comes next."),
    ("Careful Work", "Each job is prepared and carried out with attention to detail."),
    ("Local Presence", "A local company you can contact directly and talk to in person."),
    ("Respect for Your Time", "Requests are answered promptly and appointments are kept."),
    ("Honest Advice", "Recommendations are based on what you need, not on selling more."),
    ("One Point of Contact", "The same team follows your request from start to finish."),
]
TAGLINES = ["{noun_cap} you can rely on in {place}", "Practical, {approach} service in {place}",
            "Your local {noun} in {place}", "Straightforward service from {company}"]
CTAS = ["Contact Us", "Request a Quote", "Get in Touch", "Talk to Us"]


def _place(facts: dict) -> str:
    city = (facts.get("City") or "").strip().title()
    state = (facts.get("State") or "").strip().upper()
    return f"{city}, {state}" if city and state else city or state or "your area"


def write_site_copy(facts: dict, template_id: str, domain: str) -> dict:
    """Same keys as integrations/ai.SITE_SCHEMA, so the templates render it unchanged."""
    group = BY_ID[template_id].group if template_id in BY_ID else DEFAULT_GROUP
    noun, services, approach = GROUPS.get(group, GROUPS[DEFAULT_GROUP])
    rng = random.Random(f"offline|{domain.lower()}|{template_id}")
    company = (facts.get("Company") or "").strip()
    place = _place(facts)
    v = {"company": company, "place": place, "noun": noun, "noun_cap": noun[:1].upper() + noun[1:], "approach": approach}
    picked = rng.sample(services, 3)
    why = rng.sample(WHY, 3)
    tagline = rng.choice(TAGLINES).format(**v)
    about_full = "\n\n".join([
        f"{company} is a {noun} serving customers in {place}. The company works with individuals and businesses that "
        f"want a {approach} partner and a clear way of working from the first contact.",
        rng.choice([
            "Our aim is simple: understand what each customer needs, agree on a clear plan and do the work properly.",
            "We believe good service starts with listening, continues with a clear plan and ends with work done well.",
        ]),
        f"Every request is handled step by step. We explain the options, confirm the details with you and keep you "
        f"informed while the work is in progress, so there are no surprises along the way.",
        rng.choice([
            "If you would like to know whether we can help with your project, contact us and we will be glad to talk it through.",
            "We are happy to answer questions before you decide. Contact us and tell us what you have in mind.",
        ]),
    ])
    return {
        "tagline": tagline,
        "hero_subtitle": f"{company} offers {approach} service as a {noun} in {place}, with clear communication and careful work from start to finish.",
        "primary_cta": rng.choice(CTAS),
        "intro_paragraph": f"Welcome to {company}. We are a {noun} in {place} that works with customers who value clear "
                           f"communication and a {approach} approach. Tell us what you need and we will explain how we can help.",
        "services": [{"title": t, "description": d} for t, d in picked],
        "why_choose_us": [{"title": t, "description": d} for t, d in why],
        "about_short": f"{company} is a {noun} based in {place}. We focus on understanding each request, agreeing on a "
                       f"clear plan and carrying out the work in a {approach} way, keeping customers informed at every step.",
        "about_full": about_full,
        "contact_intro": f"Have a question or a project in mind? Contact {company} by phone or visit us at our address. "
                         f"We will listen to your needs and explain the next steps.",
        "footer_blurb": f"{company} — {noun} in {place}.",
        "faqs": [
            {"q": "How do I request a quote?", "a": "Contact us by phone or visit our address and tell us what you need. We will explain the next steps."},
            {"q": "Which areas do you serve?", "a": f"We are based in {place}. Contact us to confirm whether we can help in your location."},
            {"q": "How do I get started?", "a": "Get in touch and describe your request. We will talk it through with you and agree on a plan."},
            {"q": "What is included in your service?", "a": "That depends on your request. We confirm what is included with you before any work begins."},
            {"q": "How does the process work?", "a": "We listen, agree on a clear plan with you, carry out the work and keep you informed along the way."},
        ],
        "meta_description_home": f"{company}: {noun} in {place}. {approach.capitalize()} service and clear communication. Contact us to discuss your needs.",
        "meta_description_about": f"About {company}, a {noun} in {place}: how we work, what we value and how we help our customers.",
        "meta_description_contact": f"Contact {company} in {place}. Call us or visit our address to discuss your request.",
        "meta_description_faq": f"Answers to common questions about working with {company}, a {noun} in {place}.",
    }
