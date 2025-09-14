/*
 Controlling a servo position using a potentiometer (variable resistor)
 by Michal Rinott <http://people.interaction-ivrea.it/m.rinott>

 modified on 8 Nov 2013
 by Scott Fitzgerald
 http://www.arduino.cc/en/Tutorial/Knob
*/

#include <Servo.h>

Servo myservo;  // create Servo object to control a servo

int ford=1,back,ii;  // analog pin used to connect the potentiometer
int val;    // variable to read the value from the analog pin

void setup() {
  ii=90;
  myservo.attach(2);  // attaches the servo on pin 9 to the Servo object
  myservo.write(90);                  // sets the servo position according to the scaled value
  delay(1000);
  Serial.begin(9600);
}

void loop() {

if (ford==1)
{
  ii+=1;
  myservo.write(ii); 
  delay (100);
  if (ii>120)
  {
    ford=0;
    Serial.println(ii);
  }

}
else
{
  ii-=1;
  myservo.write(ii); 
  delay (100);
  if (ii<80)
  {
    ford=1;
  }
}
  

  
      
       
                       // waits for the servo to get there
}
