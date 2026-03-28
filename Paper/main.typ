#import "template.typ": project

#show: project.with(
  title: "PROJECT TITLE GOES HERE",
  authors: (
    (name: "Student Name 1", reg: "Registration Number 1"),
    (name: "Student Name 2", reg: "Registration Number 2"),
  ),
  supervisor: "Supervisor Name",
  degree: "Name of the Degree",
  date: "Month Year",
  logo: "images/logo.png",
  logo_dept: "images/logo_dept.png",
  abstract: [
    Add your abstract content here. This section should provide a concise summary of your project, including the problem addressed, the methodology used, key results, and conclusions.
  ],
  keywords: ("Keyword1", "Keyword2", "Keyword3"),
  acknowledgement: [
    Add your acknowledgements here. Thank the individuals and institutions that supported your project work.
  ],
  declaration: [
    I declare that the report entitled *“PROJECT TITLE GOES HERE”* submitted by me for the degree of Bachelor of Technology is the record of the project work carried out by me under the guidance of *“Supervisor Name”* and this work has not formed the basis for the award of any degree, diploma, associateship, fellowship, titled in this or any other University or other similar institution of higher learning.
  ],
  abbreviations: (
    ("TERM1", "Description of Term 1"),
    ("TERM2", "Description of Term 2"),
  ),
  bib_path: "references.bib",
  publications: [
    + Publication 1
    + Publication 2
  ],
  appendix_image: "images/logo.png", // Replace with your actual plagiarism report image
)

= Introduction <c1>
Add your introduction here with sample citations @paper1 and @paper2.

= Literature Review <c2>
Add your literature review here.

= Dataset and Methodology <c3>
Add your methodology here.

= Result and Analysis <c4>
Add your results and analysis here.

= Conclusion and Future Work <c5>
Add your conclusion and future work here.
