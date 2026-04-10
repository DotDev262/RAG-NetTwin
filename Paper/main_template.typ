#import "template.typ": project
#show heading.where(level: 3): set heading(outlined: false)

// ============================================================
// TEMPLATE VARIABLES - Fill in your project details here
// ============================================================

#let chancellor = "Chancellor Name"
#let admin_director = "Admin Director Name"
#let campus_director = "Campus Director Name"
#let principal = "Principal Name"
#let chairperson = "Chairperson Name"
#let assoc_prof = "Associate Professor Name"
#let program_chair = "Program Chair Name"
#let supervisor = "Supervisor Name"

// ============================================================
// PROJECT CONFIGURATION
// ============================================================

#show: project.with(
  title: "YOUR PROJECT TITLE HERE",
  authors: (
    (name: "First Author Name", reg: "REG.NO.1"),
    (name: "Second Author Name", reg: "REG.NO.2"),
    // Add more authors as needed
  ),
  supervisor: supervisor,
  chancellor: chancellor,
  admin_director: admin_director,
  campus_director: campus_director,
  principal: principal,
  chairperson: chairperson,
  assoc_prof: assoc_prof,
  program_chair: program_chair,
  degree: "Bachelor of Technology",  // B.Tech / M.Tech / PhD
  department: "Department of CSE",     // Full department name
  department_cover: "Computer Science and Engineering",  // For cover page
  date: "Month Year",
  logo: "images/logo.png",            // University logo
  logo_dept: "images/logo_dept.png",    // Department logo (optional)
  
  // ============================================================
  // ABSTRACT - Write your abstract here (150-300 words)
  // ============================================================
  abstract: [
    Your abstract goes here. It should summarize the research problem, 
    methodology, key findings, and conclusions. Keep it concise and 
    informative.
  ],
  
  // ============================================================
  // KEYWORDS - Add 4-6 keywords relevant to your research
  // ============================================================
  keywords: ("Keyword1", "Keyword2", "Keyword3", "Keyword4"),
  
  // ============================================================
  // ACKNOWLEDGEMENT - Thank contributors to your project
  // ============================================================
  acknowledgement: [
    Write your acknowledgements here. Thank supervisors, colleagues, 
    family members, and any institutions that supported your work.
  ],
  
  // ============================================================
  // DECLARATION - Standard declaration statement
  // ============================================================
  declaration: [
    We hereby declare that the project report entitled *"PROJECT TITLE"* 
    is a bona fide record of the work done by us under the guidance of 
    our supervisor. This work has not formed the basis for the award 
    of any degree, diploma, associateship, fellowship, or other similar 
    title to any candidate of any University.
  ],
  
  // ============================================================
  // ABBREVIATIONS - List of acronyms used in the report
  // ============================================================
  abbreviations: (
    ("ACL", "Access Control List"),
    ("API", "Application Programming Interface"),
    // Add more as needed
  ),
  
  // ============================================================
  // BIBLIOGRAPHY - Path to your references file
  // ============================================================
  bib_path: "references.bib",
)

// ============================================================
// MAIN CONTENT BEGINS HERE
// ============================================================

= CHAPTER TITLE <c1>

== Section 1.1
Your content goes here. The template automatically handles:
- Page numbering (Roman for front matter, Arabic for main content)
- Table of contents, list of tables, list of figures
- Proper heading styles and spacing
- First-line indent for paragraphs

Write your introduction, literature review, methodology, results, 
and conclusion in subsequent chapters.

== Section 1.2
More content here...

=== Subsection 1.2.1
Detailed content...

= CHAPTER 2 <c2>

== Overview
Continue writing your report...

// ============================================================
// Add more chapters as needed
// ============================================================

= CONCLUSION <cn>

Write your conclusions here...

// ============================================================
// REFERENCES - Automatically generated from bib_path
// ============================================================

// (No need to add anything here - handled by template)