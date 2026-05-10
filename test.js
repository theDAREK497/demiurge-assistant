const { remark } = require('remark');

const md = 'This is a link: [Test](#wiki:Some Page) here.';
const md2 = 'This is another: [Test](#wiki:Some%20Page) here.';

console.log("Spaces:", remark().processSync(md).toString());
console.log("Encoded:", remark().processSync(md2).toString());
