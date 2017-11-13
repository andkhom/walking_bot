import MySQLdb
import config

conn = MySQLdb.connect('localhost', 'root', config.DB_PASSWORD, config.DB_NAME)
conn.set_character_set('utf8')

cursor = conn.cursor()
cursor.execute('''
CREATE TABLE `route` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `date` datetime DEFAULT NULL,
  `start_location_lat` varchar(100) DEFAULT NULL,
  `start_location_lng` varchar(100) DEFAULT NULL,
  `end_location_lat` varchar(100) DEFAULT NULL,
  `end_location_lng` varchar(100) DEFAULT NULL,
  `duration` varchar(45) DEFAULT NULL,
  `distance` varchar(45) DEFAULT NULL,
  `polyline` longtext,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=92 DEFAULT CHARSET=utf8;

CREATE TABLE `step` (
  `step_id` int(11) NOT NULL AUTO_INCREMENT,
  `step_number` int(11) DEFAULT NULL,
  `route` int(11) DEFAULT NULL,
  `end_location_lat` float DEFAULT NULL,
  `end_location_lng` float DEFAULT NULL,
  `instructions` text,
  `start_location_lat` float DEFAULT NULL,
  `start_location_lng` float DEFAULT NULL,
  `polyline` longtext,
  `passed` tinyint(1) DEFAULT NULL,
  `distance` varchar(45) DEFAULT NULL,
  `duration` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`step_id`),
  KEY `idx_step_end_location_lng` (`end_location_lng`),
  KEY `step-route_idx` (`route`),
  CONSTRAINT `step-route` FOREIGN KEY (`route`) REFERENCES `route` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=5271 DEFAULT CHARSET=utf8;
''')
conn.commit()
conn.close()
