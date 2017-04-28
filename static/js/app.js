/**
 * Created by Peter.Makafan on 4/26/2017.
 */
var ViewModel = function() {
  self = this;

  self.url = ko.observable();

  self.error = ko.observable(false);

  self.loading = ko.observable(false);


  self.crawlUrl = function() {
    var jsonObj = JSON.stringify(ko.toJS({
      url: self.url
    }), null, 2);

    var jqxhr = $.ajax({
      type: 'POST',
      url: "/crawl",
      contentType: 'application/json; charset=utf-8',
      data: jsonObj,
      dataType: "json",
      beforeSend: function() {
        self.error(false);
        self.loading(true);
      },
      statusCode: {
        409: function(xhr) {

        },
        200: function(xhr) {
          var message = xhr.responseText;
          self.downloadCSV(message);
        },
        500: function(xhr) {
          self.error(true);
          self.loading(false);
        },
        400: function(xhr) {
          self.error(true);
          self.loading(false);
        },
        417: function(xhr) {
          self.error(true);
          self.loading(false);
        }
      },
      complete: function() {

      }
    });
  }

  self.downloadCSV = function(jobId) {
    var timeout = "";
    var poller = function() {
      var jqxhr = $.ajax({
        type: 'GET',
        url: "/result/" + jobId,
        beforeSend: function() {},
        success: function(data, statusCode, jqXHR) {

          if (jqXHR.status === 202) {
            console.log(data);
          } else if (jqXHR.status === 200) {
            self.url("");
            self.loading(false);
            self.error(false);
            clearTimeout(timeout);
            return false;
          }
          timeout = setTimeout(poller, 2000);
        },
        error: function(error) {
          self.error(true);
          self.loading(false);
          console.log(error)
        }
      });
    }

    poller();
  };


};

$(document).ready(function() {
  ko.applyBindings(new ViewModel());
  $(".button-collapse").sideNav();

  $('.dropdown-button').dropdown({
    inDuration: 300,
    outDuration: 225,
    constrain_width: false, // Does not change width of dropdown to that of the activator

    belowOrigin: true, // Displays dropdown below the button
    alignment: "right" // Displays dropdown with edge aligned to the left of button
  });
});
