//
// DrawPhone.com drawpad written by Ian McIntosh <ian@openanswers.org>
//
// You are free to use this code for any purpose. Please credit DrawPhone.com with a link.
//

function clamp(value, min, max) {
	if(value < min) { return min; } else if(value > max) { return max; } else{ return value; }
}

function intToHex(dec) {
	var result = (parseInt(dec).toString(16));
	if(result.length == 1) {
		result = ("0" + result);
	}
	return result.toUpperCase();
};

function initialize_drawing_canvas(canvas_node, palette_node, palette_image, pen_size_node)
{
	var KEYCODE_LEFT_BRACKET = 221;
	var KEYCODE_RIGHT_BRACKET = 219;

	var canvas = {};
	canvas.fillColor = '#000000';
	canvas.node = canvas_node;
	canvas.context = canvas_node.getContext('2d');
	canvas.radius = 0.1;
	canvas.lastUpdate = 0;

	var palette = {};
	palette.node = palette_node;
	palette.context = palette_node.getContext('2d');
	palette.render = function() {
		// Draw background image (the palette itself)
		palette.context.drawImage(palette_image, 0, 0);

		// Draw crosshair on selected color
		if(palette.latestX) {
			palette.context.beginPath();
			palette.context.strokeStyle = "#fff";
			palette.context.moveTo(palette.latestX - 4.0, palette.latestY);
			palette.context.lineTo(palette.latestX - (palette.node.width), palette.latestY);
			palette.context.moveTo(palette.latestX + 4.0, palette.latestY);
			palette.context.lineTo(palette.latestX + (palette.node.width), palette.latestY);
			palette.context.moveTo(palette.latestX, palette.latestY - 4.0);
			palette.context.lineTo(palette.latestX, palette.latestY - (palette.node.height));
			palette.context.moveTo(palette.latestX, palette.latestY + 4.0);
			palette.context.lineTo(palette.latestX, palette.latestY + (palette.node.height));
			palette.context.stroke();
		}
	};
	palette.hideCrosshairs = function() {
		palette.latestX = null;
		palette.render();
	};

	var pen_size = {};
	pen_size.node = pen_size_node;
	pen_size.context = pen_size_node.getContext('2d');
	pen_size.render = function() {
		pen_size.context.fillStyle = "#fff";
		pen_size.context.fillRect(0, 0, pen_size.node.width, pen_size.node.height);

		// Draw pen size slider < shape
		pen_size.context.beginPath();
		pen_size.context.fillStyle = "#333";
		pen_size.context.moveTo(0.1 * pen_size.node.width, 0.53 * pen_size.node.height);
		pen_size.context.lineTo(0.1 * pen_size.node.width, 0.47 * pen_size.node.height);
		pen_size.context.lineTo(0.9 * pen_size.node.width, 0.30 * pen_size.node.height);
		pen_size.context.lineTo(0.9 * pen_size.node.width, 0.60 * pen_size.node.height);
		pen_size.context.fill();

		// Draw handle (with current fillColor inside it)
		var x = (0.1 * pen_size.node.width) + (canvas.radius * pen_size.node.width * 0.8);
		var y = 0.5 * pen_size.node.height;

		pen_size.context.fillStyle = "#000";
		pen_size.context.beginPath();
		pen_size.context.moveTo(x, y);
		pen_size.context.arc(x, y, 6.0 + canvas.radius * 8, 0, Math.PI * 2, false);
		pen_size.context.fill();

		pen_size.context.fillStyle = canvas.fillColor;
		pen_size.context.beginPath();
		pen_size.context.moveTo(x, y);
		pen_size.context.arc(x, y, 4.0 + canvas.radius * 8, 0, Math.PI * 2, false);
		pen_size.context.fill();
	};

	//
	// Canvas methods
	//
	canvas.context.fillCircle = function(x, y, radius, fillColor) {
		canvas.context.fillStyle = fillColor;
		canvas.context.beginPath();
		canvas.context.moveTo(x, y);
		canvas.context.arc(x, y, radius, 0, Math.PI * 2, false);
		canvas.context.fill();
	};
	canvas.context.clearTo = function(fillColor) {
		canvas.context.fillStyle = fillColor;
		canvas.context.fillRect(0, 0, canvas.node.width, canvas.node.height);
	};
	setCurrentColor = function(color) {
		canvas.fillColor = color;

		// GUI feedback
		pen_size.render();
	};
	set_pen_size = function(size) {
		canvas.radius = size;
		pen_size.render();
	};
	canvas.pixelRadius = function() {
		return 0.5 + (canvas.radius * 50.0);
	};

	//
	// Keyboard callbacks
	//
	document.onkeydown = function(e) {
		if(e.keyCode == KEYCODE_LEFT_BRACKET && canvas.radius < 1.0) {
			canvas.radius = clamp(canvas.radius + 0.05, 0.0, 1.0);
			pen_size.render();
		}
		if(e.keyCode == KEYCODE_RIGHT_BRACKET && canvas.radius > 0.0) {
			canvas.radius = clamp(canvas.radius - 0.05, 0.0, 1.0);
			pen_size.render();
		}

		// Holding down the ] key while drawing should cause ever-larger circles
		canvas.context.fillCircle(canvas.previousX, canvas.previousY, canvas.pixelRadius(), canvas.fillColor);
	};

	//
	// Canvas callbacks
	//
	canvas.node.onmousedown = function(e) {
		canvas.lastUpdate = e.timeStamp;

		var x = e.pageX - $(this).offset().left;
		var y = e.pageY - $(this).offset().top;

		if(e.altKey || e.ctrlKey) {
			// Picking by Alt-click or Ctrl-click
			data = canvas.context.getImageData(x, y, 1, 1).data;
			setCurrentColor("#" + intToHex(data[0]) + intToHex(data[1]) + intToHex(data[2]));
			palette.hideCrosshairs();
		} else if(e.shiftKey) {

		} else {
			// Draw the first point
			canvas.isDrawing = true;
			canvas.context.fillCircle(x, y, canvas.pixelRadius(), canvas.fillColor);
		}
	};
	canvas.node.mouseMoveHandler = function(e) {
		if(canvas.isDrawing) {
			var x = e.pageX - $(this).offset().left;
			var y = e.pageY - $(this).offset().top;

			var deltaX = (x - canvas.previousX);
			var deltaY = (y - canvas.previousY);
			var delta = Math.sqrt((deltaX*deltaX) + (deltaY*deltaY));
			var timeDelta = (e.timeStamp - canvas.lastUpdate);

			if(timeDelta > 100) {		// && delta > 8.0) {
				// Avoid drawing when there's a big lag and a big gap (probably due to Javascript GC)
			}
			else {
				if(canvas.previousX != false) {
					// from previous to current
					var frequency = 3;		// number of times to stamp circle per 'radius' pixels the pen travels
					var numPoints = clamp(((delta / canvas.pixelRadius()) * frequency), 1, 30);
					for(i=0 ; i<numPoints ; i++) {
						canvas.context.fillCircle((canvas.previousX + (i+1) * ((x-canvas.previousX) / numPoints)), (canvas.previousY + (i+1) * ((y-canvas.previousY) / numPoints)), canvas.pixelRadius(), canvas.fillColor);
					}
				}
				else {
					canvas.context.fillCircle(x, y, canvas.pixelRadius(), canvas.fillColor);
				}
			}
			canvas.lastUpdate = e.timeStamp;
		}
		canvas.previousX = x;
		canvas.previousY = y;
	};
	// Pipe mouse messages from the whole page to the canvas
	document.body.onmousemove = function(e) { return canvas.node.mouseMoveHandler(e); };
	document.body.onmouseup = function(e) {
		canvas.isDrawing = false;
	};

	//
	// Palette callbacks
	//
	palette.node.onmousemove = function(e) {
		var x = e.pageX - $(this).offset().left;
		var y = e.pageY - $(this).offset().top;
		palette.latestX = x;
		palette.latestY = y;

		if(palette.isPicking) {
			data = palette.context.getImageData(palette.latestX, palette.latestY, 1, 1).data;
			setCurrentColor("#" + intToHex(data[0]) + intToHex(data[1]) + intToHex(data[2]));
			palette.render();
		}
	};
	palette.node.onmousedown = function(e) {
		palette.isPicking = true;
		data = palette.context.getImageData(palette.latestX, palette.latestY, 1, 1).data;
		setCurrentColor("#" + intToHex(data[0]) + intToHex(data[1]) + intToHex(data[2]));
		palette.render();
	};
	palette.node.onmouseup = function(e) {
		palette.isPicking = false;
	};
	palette.node.onmouseout = function(e) {
		palette.isPicking = false;
	};

	//
	// Pen Size helpers
	//
	pen_size.xToProgress = function(x) {
		return clamp((((x / (pen_size.node.width+1)) - 0.1) / 0.8), 0.0, 1.0);
	};

	//
	// Pen Size callbacks
	//
	pen_size.node.onmousedown = function(e) {
		var x = e.pageX - $(this).offset().left;
		set_pen_size(pen_size.xToProgress(x));
		pen_size.mouseDown = true;
	};
	pen_size.node.onmousemove = function(e) {
		if(pen_size.mouseDown) {
			var x = e.pageX - $(this).offset().left;
			set_pen_size(pen_size.xToProgress(x));
		}
	};
	pen_size.node.onmouseup = function(e) {
		pen_size.mouseDown = false;
	};
	pen_size.node.onmouseout = function(e) {
		pen_size.mouseDown = false;
	};

	//
	// Render everything once to begin
	//
	pen_size.render();
	palette.render();
	// Keep canvas transparent ... canvas.context.clearTo("#FCFCFC");
}
