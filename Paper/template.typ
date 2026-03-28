
#let project(
  title: "",
  authors: (),
  supervisor: "",
  department: "Department of Computer Science and Engineering",
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
  set par(leading: 0.65em, justify: true) // Approx 1.25-1.5 line spacing
  
  // Header styling
  show heading: set text(weight: "bold")
  set heading(numbering: "1.1")
  
  // Custom Chapter styling
  show heading.where(level: 1): it => {
    if it.numbering != none {
      pagebreak(weak: true)
      v(2em)
      set align(center)
      set text(size: 14pt)
      [CHAPTER-#counter(heading).display()]
      v(0.5em)
      upper(it.body)
      v(1em)
    } else {
      pagebreak(weak: true)
      v(2em)
      set align(center)
      set text(size: 14pt)
      upper(it.body)
      v(1em)
    }
  }

  // --- 1. Cover Page ---
  set page(margin: 1in)
  page(numbering: none)[
    #set align(center)
    #set text(size: 14pt)
    #set par(leading: 0.8em) // 1.5 spacing
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
    #text(style: "italic")[in partial fulfilment for the award of the \ degree of]
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
    
    #text(size: 14pt, weight: "bold")[BONAFIDE CERTIFICATE]
    #v(1.5em)
    
    #set align(left)
    #set par(first-line-indent: 2em, justify: true, leading: 0.8em)
    This is to certify that this project report entitled *"#title"* is the bonafide work of *"#authors.map(a => [#a.name (#a.reg)]).join(" & ")"* who carried out the project work under my supervision.
    
    #v(4fr)
    
    #grid(
      columns: (1fr, 1fr),
      gutter: 1.5em,
      align(left)[
        #text(weight: "bold")[Dr. BHAGAVATHI PRIYA] \
        #text(weight: "bold")[CHAIRPERSON] \ \
        #text(size: 11pt)[
          #department \
          #school \
          #university \
          #location
        ]
      ],
      align(left)[
        #text(weight: "bold")[#supervisor] \
        #text(weight: "bold")[SUPERVISOR] \ \
        #text(size: 11pt)[
          Assistant Professor(Sr.G), \
          #department \
          #school \
          #university \
          #location
        ]
      ]
    )
    
    #v(2.5fr)
    
    #grid(
      columns: (1fr, 1fr),
      gutter: 1.5em,
      align(left)[
        #text(weight: "bold")[INTERNAL EXAMINER]
      ],
      align(left)[
        #text(weight: "bold")[EXTERNAL EXAMINER]
      ]
    )
    #v(0.5fr)
  ]

  // --- 4. Declaration ---
  page()[
    #set align(center)
    #if logo_dept != none { image(logo_dept, width: 60%) }
    #v(2em)
    #text(size: 14pt, weight: "bold")[DECLARATION BY THE CANDIDATE]
    #v(1.5em)
    
    #set align(left)
    #set par(first-line-indent: 2em, justify: true, leading: 0.8em)
    #declaration
    #v(4fr)
    #grid(
      columns: (1fr, 1fr),
      gutter: 1.5em,
      [],
      align(center)[
        #authors.map(a => [
          #v(5em)
          #text(weight: "bold")[SIGNATURE] \
          #text(weight: "bold")[#a.name] \
          (#a.reg)
        ]).join()
      ]
    )
  ]

  // --- 5. Abstract ---
  heading(numbering: none, outlined: true)[Abstract]
  abstract
  if keywords != () {
    v(1em)
    [*Keywords:* ]
    keywords.map(k => [_#k _]).join(", ")
  }
  pagebreak()

  // --- 6. Acknowledgement ---
  heading(numbering: none, outlined: true)[Acknowledgement]
  acknowledgement
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
      inset: (y: 8pt),
      align: (left, left, right),
      [*CHAPTER* \ *NO.*], [*TITLE*], [*PAGE* \ *NO.*]
    )
    v(-0.5em)
    line(length: 100%, stroke: 0.5pt)
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
          ("", upper(it.element.body), it => it)
        }
      } else {
        ("", num + " " + upper(it.element.body), it => it)
      }
      
      grid(
        columns: (80pt, 1fr, 60pt),
        gutter: 0pt,
        inset: (y: 6pt),
        align: (left, left, right),
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
      inset: (y: 8pt),
      align: (left, left, right),
      [*TABLE* \ *NO.*], [*TITLE*], [*PAGE* \ *NO.*]
    )
    v(-0.5em)
    line(length: 100%, stroke: 0.5pt)
    v(0.5em)

    show outline.entry: it => {
      let loc = it.element.location()
      let num = numbering(it.element.numbering, ..counter(figure.where(kind: table)).at(loc))
      let title = if it.element.caption != none { upper(it.element.caption.body) } else { "" }
      
      grid(
        columns: (80pt, 1fr, 60pt),
        gutter: 0pt,
        inset: (y: 6pt),
        align: (left, left, right),
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
      inset: (y: 8pt),
      align: (left, left, right),
      [*FIGURE* \ *NO.*], [*TITLE*], [*PAGE* \ *NO.*]
    )
    v(-0.5em)
    line(length: 100%, stroke: 0.5pt)
    v(0.5em)

    show outline.entry: it => {
      let loc = it.element.location()
      let num = numbering(it.element.numbering, ..counter(figure.where(kind: image)).at(loc))
      let title = if it.element.caption != none { upper(it.element.caption.body) } else { "" }
      
      grid(
        columns: (80pt, 1fr, 60pt),
        gutter: 0pt,
        inset: (y: 6pt),
        align: (left, left, right),
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
      ..abbreviations.map(a => ([#a.at(0)], [-], [#a.at(1)])).flatten()
    )
    pagebreak()
  }

  // --- Main Content Setup ---
  set page(margin: 1in, numbering: "1")
  counter(page).update(1)
  
  body

  if bib_path != none {
    heading(level: 1, numbering: "1.1", outlined: true)[References]
    bibliography(bib_path, title: none, style: "apa")
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
