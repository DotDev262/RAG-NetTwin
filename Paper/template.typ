#let project(
  title: "",
  authors: (),
  supervisor: "",
  internal_examiner_1: "",
  internal_examiner_2: "",
  chancellor: "Sri Mata Amritanandamayi Devi",
  admin_director: "",
  campus_director: "",
  principal: "Dr. V. Jayakumar",
  chairperson: "Dr. S. Baghavathi Priya",
  assoc_prof: "",
  program_chair: "Dr. S. Natarajan",
  department: "Department of CSE",
  department_cover: "Computer Science and Engineering",
  school: "Amrita School of Computing",
  university: "Amrita Vishwa Vidyapeetham",
  location: "Chennai - 601103",
  date: "March 2026",
  logo: none,
  logo_dept: none,
  abstract: [],
  keywords: (),
  acknowledgement: [],
  declaration: [],
  abbreviations: (),
  degree: "Bachelor of Technology",
  bib_path: none,
  publications: [],
  appendix_image: none,
  body
) = {
  // --- Global Settings ---
  set document(title: title, author: authors.map(a => a.name))
  set page(
    paper: "a4",
    margin: 1in,
    numbering: "i",
    number-align: bottom + center,
  )
  set text(font: "Times New Roman", size: 12pt)
  
  // Header styling
  show heading: set text(weight: "bold")
  set heading(numbering: "1.1")
  set figure(
    numbering: n => numbering("1.1", counter(heading).at(here()).at(0), n),
    supplement: "Figure"
  )
  show figure.where(kind: table): set figure(
    numbering: n => numbering("1.1", counter(heading).at(here()).at(0), n),
    supplement: "Table"
  )
  show figure.where(kind: table): it => {
    set align(center)
    v(12.5pt, weak: true)
    if it.has("caption") {
      it.caption
      v(10pt, weak: true)
    }
    it.body
    v(12.5pt, weak: true)
  }
  show figure: set block(breakable: false)
  show table.cell.where(y: 0): set align(center)

  // Helper for "Capitalize Each Word" (Title Case)
  let title-case(it) = {
    if type(it) == "string" {
      it.split(" ").map(w => {
        if w.len() > 0 {
          upper(w.slice(0, 1)) + w.slice(1)
        } else { "" }
      }).join(" ")
    } else if it.has("body") {
      title-case(it.body)
    } else if it.has("text") {
      title-case(it.text)
    } else {
      it
    }
  }

  // Helper to uppercase name without affecting titles (Dr., Mrs., Mr., Ms., Prof.)
  let name-case(name) = {
    let titles = ("Dr.", "Mrs.", "Mr.", "Ms.", "Prof.")
    let parts = name.split(" ")
    if parts.len() > 0 and parts.at(0) + "." in titles {
      parts.at(0) + ". " + parts.slice(1).map(p => upper(p)).join(" ")
    } else if parts.len() > 0 and parts.at(0) in titles {
      parts.at(0) + " " + parts.slice(1).map(p => upper(p)).join(" ")
    } else {
      upper(name)
    }
  }

  show heading.where(level: 2): it => context {
    let before = query(selector(heading).before(here()))
    let is_first = if before.len() > 0 { before.last().level == 1 } else { false }
    v(if is_first { 0.3em } else { 1.5em }, weak: true)
    set text(size: 12pt, weight: "bold")
    set align(left)
    it
    v(0.2em)
  }

  show heading.where(level: 3): it => {
    v(1.2em, weak: true)
    set text(size: 12pt, weight: "bold")
    set align(left)
    it
    v(0.5em)
  }
  
  // Custom Chapter styling
  show heading.where(level: 1): it => {
    counter(figure.where(kind: image)).update(0)
    counter(figure.where(kind: table)).update(0)
    set align(center)
    set text(size: 14pt, weight: "bold")
    if it.numbering != none {
      pagebreak(weak: true)
      v(2em)
      [CHAPTER #counter(heading).display()]
v(0.2em)
      upper(it.body)
      v(0.3em)
    } else {
      pagebreak(weak: true)
      v(2em)
      upper(it.body)
      v(0.3em)
    }
  }

  // --- 1. Cover Page ---
  set page(margin: 1in)
  page(numbering: none)[
    #set align(center)
    #set text(size: 14pt)
    #set par(leading: 0.8em) // Original front-matter spacing
    #block(spacing: 0.5em)[
      #text(size: 18pt, weight: "bold")[#upper(title)]
    ]
    
    #v(0.6em)
    #text(weight: "bold")[A PROJECT REPORT]
    
    #v(0.6em)
    #text(style: "italic")[Submitted to]
    #v(0.2em)
    #text(size: 16pt, weight: "bold")[#university]
    
    #v(0.2em)
    #text(style: "italic")[in partial fulfilment for the award of the degree of]
    #v(0.4em)
    #text(size: 14pt, weight: "bold")[#upper(degree) \ IN \
    #upper(department_cover)]
    
    #v(0.6em)
    #text(weight: "bold")[By]
    #v(0.6em)
    
    #grid(
      columns: (1fr),
      gutter: 1.5em,
      ..authors.map(a => [
        #text(weight: "bold")[#upper(a.name)] \
        (#text(weight: "bold")[Reg. No. #a.reg])
      ])
    )
    
    #v(0.8em)
    #text(style: "italic", weight: "bold")[Supervisor] \
    #v(0.2em)
    #text(weight: "bold")[#supervisor]
    #v(0.8em)
    #if logo != none { image(logo, height: 2.5cm) } else { rect(width: 40%, height: 2cm, stroke: 0.5pt)[LOGO] }
    
    #v(0.8em)
    #text(size: 16pt, weight: "bold")[#upper(university)] \
    #text(size: 16pt, weight: "bold")[#upper(school)] \
    #text(size: 16pt, weight: "bold")[#upper(location)] \
    #text(weight: "bold")[#date]
    
    #v(0.5fr)
    #text(size: 10pt)[i]
  ]

  // --- 2. Bonafide Page ---
  set page(margin: 1in)
  page()[
    #set align(center)
    #v(0.5em)
    #if logo_dept != none { image(logo_dept, height: 2.2cm) } else if logo != none { image(logo, height: 2.2cm) }
    #v(1em)
    
    #text(size: 16pt, weight: "bold")[BONAFIDE CERTIFICATE]
    #v(1.5em)
    
    #set align(left)
    #set par(first-line-indent: 0pt, justify: true, leading: 0.8em)
    #set text(size: 14pt)
    This is to certify that this project report entitled *"#title"* is the bonafide work of *"#authors.map(a => [#a.name (#a.reg)]).join(" and ")"* who carried out the project work under my supervision.
    
    #v(2fr)
    
    #grid(
      columns: (1fr, 1fr),
      gutter: 1.5em,
      {
        set par(first-line-indent: 0pt)
        align(left)[
          #v(3em)
          #text(size: 12pt, weight: "bold")[SIGNATURE] \
          #v(1em)
          #text(size: 14pt, weight: "bold")[#name-case(chairperson)] \
          #text(size: 12pt, weight: "bold")[CHAIRPERSON] \
          #text(size: 12pt)[
            #department \
            #school \
            #university \
            #location
          ]
        ]
      },
      {
        set par(first-line-indent: 0pt)
        align(right)[
          #v(3em)
          #text(size: 12pt, weight: "bold")[SIGNATURE] \
          #v(1em)
          #text(size: 14pt, weight: "bold")[#name-case(supervisor)] \
          #text(size: 12pt, weight: "bold")[SUPERVISOR] \
          #text(size: 12pt)[
            #department \
            #school \
            #university \
            #location
          ]
        ]
      }
    )
    
    #v(2.5fr)
    
    #grid(
      columns: (1fr, 1fr),
      gutter: 1.5em,
      {
        set par(first-line-indent: 0pt)
        align(left)[
          #v(3em)
          #text(size: 14pt, weight: "bold")[INTERNAL EXAMINER]
        ]
      },
      {
        set par(first-line-indent: 0pt)
        align(right)[
          #v(3em)
          #text(size: 14pt, weight: "bold")[INTERNAL EXAMINER]
        ]
      }
    )
    
    #v(1em)
  ]

  // --- 4. Declaration ---
  page()[
    #set align(center)
    #if logo_dept != none { image(logo_dept, width: 60%) }
    #v(2em)
    #text(size: 16pt, weight: "bold")[DECLARATION BY THE CANDIDATE]
    #v(1.5em)
    
    #set align(left)
    #set par(first-line-indent: 0pt, justify: true, leading: 0.8em)
    #text(size: 14pt)[#declaration]
    #v(4fr)
    #grid(
      columns: (1fr, 1fr),
      gutter: 1.5em,
      [],
      align(right)[
        #v(5em)
        #text(size: 14pt, weight: "bold")[SIGNATURE] \
        #v(0.5em)
        #box(width: 10cm, text(size: 12pt, weight: "bold", hyphenate: false)[#authors.at(0).name & #authors.at(1).name]) \
        #v(0.3em)
        #box(width: 10cm, text(size: 12pt, weight: "bold", hyphenate: false)[(#authors.at(0).reg) & (#authors.at(1).reg)])
      ]
    )
  ]

  // --- 5. Abstract ---
  heading(numbering: none, outlined: true)[Abstract]
  text(size: 14pt)[
    #set par(justify: true)
    #abstract
  ]
  if keywords != () {
    v(1em)
    [*Keywords:* ]
    keywords.map(k => [_#k _]).join(", ")
  }
  pagebreak()

  // --- 6. Acknowledgement ---
  heading(numbering: none, outlined: true)[Acknowledgement]
  text(size: 14pt)[
    #set par(justify: true)
    #acknowledgement
  ]
  v(3fr)
  grid(
    columns: (1fr, 1fr),
    gutter: 1.5em,
    [],
    align(center)[
      #authors.map(a => [
        #v(1em)
        #text(weight: "bold")[#a.name] \
        (#a.reg)
      ]).join()
    ]
  )
  pagebreak()

  // --- 7. Table of Contents & Lists ---
  set page(margin: 1in)
  {
    heading(numbering: none, outlined: false)[TABLE OF CONTENTS]
    
    // Header for the TOC
    grid(
      columns: (80pt, 1fr, 60pt),
      gutter: 0pt,
      inset: (y: 0.5em),
      align: center,
      [*CHAPTER* \ *NO.*], [*TITLE*], [*PAGE* \ *NO.*]
    )
    v(0.5em)

    show outline.entry: it => {
      let loc = it.element.location()
      let num = if it.element.has("numbering") and it.element.numbering != none {
        numbering(it.element.numbering, ..counter(heading).at(loc))
      } else { "" }
      
      let (col1, col2, pg_style) = if it.level == 1 {
        if num != "" {
          (strong(num), strong(upper(it.element.body)), it => it)
        } else {
          ("", strong(it.element.body), it => it)
        }
      } else {
        ("", num + " " + upper(it.element.body), it => it)
      }
      
      grid(
        columns: (80pt, 1fr, 60pt),
        gutter: 0pt,
        inset: (y: 0.5em),
        align: (center, left, center),
        col1, col2, pg_style(it.page())
      )
    }
    
    outline(title: none)
  }
  pagebreak()
  
  {
    heading(numbering: none, outlined: true)[List of Tables]
    
    // Header for LOT
    grid(
      columns: (80pt, 1fr, 60pt),
      gutter: 0pt,
      inset: (y: 0.5em),
      align: center,
      [*TABLE* \ *NO.*], [*TITLE*], [*PAGE* \ *NO.*]
    )
    v(0.5em)

    show outline.entry: it => {
      let loc = it.element.location()
      let ch = counter(heading).at(loc).at(0)
      let fig = counter(figure.where(kind: table)).at(loc).at(0)
      let num = [#ch.#fig]
      let title = if it.element.caption != none { upper(it.element.caption.body) } else { "" }
      
      grid(
        columns: (80pt, 1fr, 60pt),
        gutter: 0pt,
        inset: (y: 0.5em),
        align: (center, left, center),
        [#num], [#title], [#it.page()]
      )
    }
    outline(title: none, target: figure.where(kind: table))
  }
  pagebreak()
  
  {
    heading(numbering: none, outlined: true)[List of Figures]
    
    // Header for LOF
    grid(
      columns: (80pt, 1fr, 60pt),
      gutter: 0pt,
      inset: (y: 0.5em),
      align: center,
      [*FIGURE* \ *NO.*], [*TITLE*], [*PAGE* \ *NO.*]
    )
    v(0.5em)

    show outline.entry: it => {
      let loc = it.element.location()
      let ch = counter(heading).at(loc).at(0)
      let fig = counter(figure.where(kind: image)).at(loc).at(0)
      let num = [#ch.#fig]
      let title = if it.element.caption != none { upper(it.element.caption.body) } else { "" }
      
      grid(
        columns: (80pt, 1fr, 60pt),
        gutter: 0pt,
        inset: (y: 0.5em),
        align: (center, left, center),
        [#num], [#title], [#it.page()]
      )
    }
    outline(title: none, target: figure.where(kind: image))
  }
  pagebreak()
  
  if abbreviations != () {
    heading(numbering: none, outlined: true)[List of Symbols and Abbreviations]
    grid(
      columns: (60pt, 20pt, 1fr),
      align: (left, left),
      gutter: 1em,
      ..abbreviations.map(a => ([*#a.at(0)*], [-], [#a.at(1)])).flatten()
    )
    pagebreak()
  }

  // --- Main Content Setup ---
  set page(margin: 1in, numbering: "1")
  counter(page).update(1)
  
  // --- Explicit Paragraph Styling for Main Body ---
  set par(leading: 1.5em, justify: true, first-line-indent: 1cm)
  show heading: it => it + h(0pt) // Safely triggers indentation on the next paragraph
  
  body

  if bib_path != none {
    heading(numbering: none, outlined: true)[#upper([References])]
    set par(first-line-indent: 0pt, justify: false)
    bibliography(bib_path, title: none, style: "ieee_sorted.csl", full: true)
  }

  if publications != [] {
    pagebreak()
    heading(numbering: none, outlined: true)[LIST OF PUBLICATIONS]
    publications
  }

  if appendix_image != none {
    pagebreak()
    heading(numbering: none, outlined: false)[APPENDIX - PLAGIARISM REPORT]
    figure(
      image(appendix_image, width: 90%),
      outlined: false,
    )
  }
}
